import logging

from app.sources.base import ObservationPoint, SourceAdapter, SourceFetchError, SourceUnavailableError, retrying_get

logger = logging.getLogger(__name__)

# ECB Statistical Data Warehouse (SDW) SDMX REST API. Public, no API key.
# Docs: https://data.ecb.europa.eu/help/api/data
# Dataflow/series keys below give euro-area-level series (these countries
# share a single monetary policy so IR/LTY are area-wide, not per-country;
# CPI/GDP/UNEMP do have national breakdowns via the ICP/MNA/UNE dataflows).
BASE_URL = "https://data-api.ecb.europa.eu/service/data"

# Countries in our registry that use the euro and therefore ride the shared
# ECB policy-rate / bond-yield series, keyed by ISO2 used in ECB series codes.
_EURO_ISO2 = {
    "DEU": "DE",
    "FRA": "FR",
    "ITA": "IT",
    "ESP": "ES",
}

# dataflow, series-key template per indicator. {iso2} is substituted where
# the series is country-specific; area-wide series have no placeholder.
_SERIES_MAP = {
    "IR": ("FM", "B.U2.EUR.4F.KR.MRR_FR.LEV"),            # ECB main refinancing rate (area-wide)
    "LTY": ("IRS", "M.{iso2}.L.L40.CI.0000.EUR.N.Z"),       # 10Y govt benchmark yield, monthly
    "CPI": ("ICP", "M.{iso2}.N.000000.4.ANR"),              # HICP all-items, annual rate
    "GDP": ("MNA", "Q.Y.{iso2}.W2.S1.S1.B.B1GQ._Z._Z._Z.EUR.LR.GY"),  # real GDP, y/y growth
    "UNEMP": ("UNE", "M.{iso2}.S.UNEHRT.TOTAL0.15_74.T"),   # unemployment rate, total
}


class EcbAdapter(SourceAdapter):
    name = "ecb"

    def fetch(self, *, country_iso3: str, indicator_type: str, start_date: str, end_date: str) -> list[ObservationPoint]:
        iso2 = _EURO_ISO2.get(country_iso3)
        if not iso2:
            raise SourceUnavailableError(f"{country_iso3} is not covered by the ECB adapter")

        mapping = _SERIES_MAP.get(indicator_type)
        if not mapping:
            raise SourceUnavailableError(f"No ECB series mapped for indicator {indicator_type}")

        dataflow, key_template = mapping
        series_key = key_template.format(iso2=iso2)
        url = f"{BASE_URL}/{dataflow}/{series_key}"
        params = {
            "startPeriod": start_date,
            "endPeriod": end_date,
            "format": "jsondata",
        }

        try:
            resp = retrying_get(url, params=params, headers={"Accept": "application/json"})
            payload = resp.json()
        except Exception as e:
            raise SourceFetchError(f"ECB request failed for {series_key}: {e}") from e

        points = self._parse_sdmx_json(payload)
        return self._clean_and_sort(points)

    @staticmethod
    def _parse_sdmx_json(payload: dict) -> list[ObservationPoint]:
        """ECB SDW returns SDMX-JSON: observation index -> value, plus a
        separate time-period dimension we have to zip back together."""
        points: list[ObservationPoint] = []
        try:
            structure = payload["structure"]
            time_dim = next(
                d for d in structure["dimensions"]["observation"] if d["id"] == "TIME_PERIOD"
            )
            periods = [v["id"] for v in time_dim["values"]]

            datasets = payload["dataSets"]
            if not datasets:
                return []
            series = datasets[0].get("series", {})
            for _series_key, series_val in series.items():
                observations = series_val.get("observations", {})
                for obs_idx, obs_val in observations.items():
                    period = periods[int(obs_idx)]
                    value = obs_val[0]
                    if value is None:
                        continue
                    date = EcbAdapter._period_to_date(period)
                    if date:
                        points.append(ObservationPoint(date=date, value=float(value)))
        except (KeyError, IndexError, StopIteration, TypeError, ValueError) as e:
            raise SourceFetchError(f"Could not parse ECB SDMX-JSON response: {e}") from e
        return points

    @staticmethod
    def _period_to_date(period: str) -> str | None:
        """Normalize ECB period strings ('2023', '2023-Q1', '2023-04') to an
        ISO date (first day of the period)."""
        try:
            if len(period) == 4:  # annual
                return f"{period}-01-01"
            if "Q" in period:  # e.g. 2023-Q1
                year, q = period.split("-Q")
                month = (int(q) - 1) * 3 + 1
                return f"{year}-{month:02d}-01"
            if len(period) == 7:  # monthly, e.g. 2023-04
                return f"{period}-01"
            return period
        except Exception:
            return None
