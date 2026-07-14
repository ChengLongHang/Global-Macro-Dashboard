import logging

import pandas as pd

from app.sources.base import ObservationPoint, SourceAdapter, SourceFetchError, SourceUnavailableError, retrying_get

logger = logging.getLogger(__name__)

try:
    import imfp
    IMFP_AVAILABLE = True
except ImportError:
    IMFP_AVAILABLE = False
    logger.warning("imfp package not available - install with `pip install imfp` for IMF coverage")

# NOTE: IMF has moved most public access to a newer Data API
# (https://data.imf.org / dataservices.imf.org SDMX2.1 successor). The
# legacy CompactData REST endpoint used below as a fallback may be retired;
# verify against https://datahelpdesk.imf.org before relying on it in
# production, and prefer the World Bank adapter as primary fallback if IMF
# access is unreliable.
_LEGACY_BASE_URL = "https://dataservices.imf.org/REST/SDMX_JSON.svc/CompactData"

_IMFP_PARAMS = {
    "CPI": {
        "database_id": "CPI",
        "index_type": ["CPI"],
        "coicop_1999": ["_T"],
        "type_of_transformation": ["IX"],
        "frequency": ["M"],
    },
    "GDP": {
        "database_id": "WEO",
        "indicator": ["NGDP_RPCH"],
        "frequency": ["A"],
    },
    "UNEMP": {
        "database_id": "LS",
        "indicator": ["U"],
        "type_of_transformation": ["PT"],
        "frequency": ["M"],
    },
}

_LEGACY_SERIES_MAP = {
    "CPI": ("CPI", "PCPI_IX"),
    "GDP": ("WEO", "NGDP_RPCH"),
    "UNEMP": ("LS", "LUR"),
}


class ImfAdapter(SourceAdapter):
    name = "imf"

    def fetch(self, *, country_iso3: str, indicator_type: str, start_date: str, end_date: str) -> list[ObservationPoint]:
        if indicator_type not in _IMFP_PARAMS:
            raise SourceUnavailableError(f"IMF has no series mapped for indicator {indicator_type}")

        if IMFP_AVAILABLE:
            try:
                points = self._fetch_via_imfp(country_iso3, indicator_type, start_date, end_date)
                if points:
                    return points
            except Exception as e:
                logger.warning(f"imfp fetch failed for {indicator_type}/{country_iso3}, trying legacy API: {e}")

        return self._fetch_via_legacy_api(country_iso3, indicator_type, start_date, end_date)

    def _fetch_via_imfp(self, country_iso3: str, indicator_type: str, start_date: str, end_date: str) -> list[ObservationPoint]:
        params = dict(_IMFP_PARAMS[indicator_type])
        params["country"] = [country_iso3]
        params["start_year"] = int(start_date[:4])

        df = imfp.imf_dataset(**params)
        if df is None or df.empty or "time_period" not in df.columns or "obs_value" not in df.columns:
            return []

        df = df.copy()
        df["time_period"] = df["time_period"].astype(str).str.replace("-M", "-")
        df["time_period"] = pd.to_datetime(df["time_period"], errors="coerce")
        df["obs_value"] = pd.to_numeric(df["obs_value"], errors="coerce")
        df = df.dropna(subset=["time_period", "obs_value"])

        start_dt, end_dt = pd.to_datetime(start_date), pd.to_datetime(end_date)
        df = df[(df["time_period"] >= start_dt) & (df["time_period"] <= end_dt)]

        points = [
            ObservationPoint(date=row.time_period.strftime("%Y-%m-%d"), value=float(row.obs_value))
            for row in df.itertuples(index=False)
        ]
        return self._clean_and_sort(points)

    def _fetch_via_legacy_api(self, country_iso3: str, indicator_type: str, start_date: str, end_date: str) -> list[ObservationPoint]:
        mapping = _LEGACY_SERIES_MAP.get(indicator_type)
        if not mapping:
            return []
        dataset, series_suffix = mapping
        series = f"{country_iso3}.{series_suffix}"
        url = f"{_LEGACY_BASE_URL}/{dataset}/{series}"
        params = {"startPeriod": start_date, "endPeriod": end_date}

        try:
            resp = retrying_get(url, params=params)
            data = resp.json()
        except Exception as e:
            raise SourceFetchError(f"IMF legacy request failed for {series}: {e}") from e

        points: list[ObservationPoint] = []
        start_dt, end_dt = pd.to_datetime(start_date), pd.to_datetime(end_date)

        series_list = data.get("CompactData", {}).get("DataSet", {}).get("Series", [])
        if isinstance(series_list, dict):
            series_list = [series_list]

        for s in series_list:
            obs = s.get("Obs", [])
            if isinstance(obs, dict):
                obs = [obs]
            for o in obs:
                time, value = o.get("TIME_PERIOD"), o.get("OBS_VALUE")
                if time is None or value is None:
                    continue
                dt = pd.to_datetime(time, errors="coerce")
                val = pd.to_numeric(value, errors="coerce")
                if pd.notna(dt) and pd.notna(val) and start_dt <= dt <= end_dt:
                    points.append(ObservationPoint(date=dt.strftime("%Y-%m-%d"), value=float(val)))

        return self._clean_and_sort(points)
