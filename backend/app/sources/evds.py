import logging

from app.core.config import settings
from app.sources.base import ObservationPoint, SourceAdapter, SourceFetchError, SourceUnavailableError, retrying_get

logger = logging.getLogger(__name__)

# Central Bank of the Republic of Turkey (CBRT) - EVDS (Electronic Data
# Delivery System) API. Requires a free API key (EVDS_API_KEY) --
# register at https://evds2.tcmb.gov.tr
BASE_URL = "https://evds2.tcmb.gov.tr/service/evds/series={series}&startDate={start}&endDate={end}&type=json"

_SERIES_MAP = {
    "IR": "TP.PPK01",       # CBRT 1-week repo (policy) rate
    "CPI": "TP.FG.J0",      # CPI index
    "UNEMP": "TP.TIG09",    # Unemployment rate
}


class EvdsAdapter(SourceAdapter):
    name = "evds"

    def fetch(self, *, country_iso3: str, indicator_type: str, start_date: str, end_date: str) -> list[ObservationPoint]:
        if country_iso3 != "TUR":
            raise SourceUnavailableError("EVDS adapter only covers TUR")

        series = _SERIES_MAP.get(indicator_type)
        if not series:
            raise SourceUnavailableError(f"No EVDS series mapped for indicator {indicator_type}")

        if not settings.evds_api_key:
            raise SourceFetchError("EVDS_API_KEY is not configured")

        url = BASE_URL.format(
            series=series,
            start=self._to_evds_date(start_date),
            end=self._to_evds_date(end_date),
        )
        headers = {"key": settings.evds_api_key}

        try:
            resp = retrying_get(url, headers=headers)
            payload = resp.json()
        except Exception as e:
            raise SourceFetchError(f"EVDS request failed for {series}: {e}") from e

        items = payload.get("items", [])
        value_key = series.replace(".", "_")  # EVDS flattens dots to underscores in field names
        points: list[ObservationPoint] = []
        for row in items:
            date_str = row.get("Tarih")  # e.g. "01-2023" or "01-01-2023" depending on frequency
            raw_value = row.get(value_key)
            if not date_str or raw_value in (None, ""):
                continue
            date = self._parse_evds_date(date_str)
            if not date:
                continue
            try:
                points.append(ObservationPoint(date=date, value=float(raw_value)))
            except ValueError:
                continue

        return self._clean_and_sort(points)

    @staticmethod
    def _to_evds_date(iso_date: str) -> str:
        y, m, d = iso_date.split("-")
        return f"{d}-{m}-{y}"

    @staticmethod
    def _parse_evds_date(date_str: str) -> str | None:
        parts = date_str.split("-")
        try:
            if len(parts) == 2:   # monthly "MM-YYYY"
                m, y = parts
                return f"{y}-{m}-01"
            if len(parts) == 3:   # daily "DD-MM-YYYY"
                d, m, y = parts
                return f"{y}-{m}-{d}"
        except ValueError:
            return None
        return None
