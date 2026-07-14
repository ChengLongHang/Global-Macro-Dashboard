import logging

from app.sources.base import ObservationPoint, SourceAdapter, SourceFetchError, SourceUnavailableError, retrying_get

logger = logging.getLogger(__name__)

# World Bank API. Public, no key. Docs: https://datahelpdesk.worldbank.org/knowledgebase/articles/889392
# This is our broadest-coverage fallback -- every G20 country has an ISO3
# code recognized here, though series are typically annual, which is coarser
# than central-bank monthly data.
BASE_URL = "https://api.worldbank.org/v2/country/{iso3}/indicator/{indicator}"

_INDICATOR_MAP = {
    "CPI": "FP.CPI.TOTL.ZG",       # Inflation, consumer prices (annual %)
    "GDP": "NY.GDP.MKTP.KD.ZG",     # GDP growth (annual %)
    "UNEMP": "SL.UEM.TOTL.ZS",      # Unemployment, total (% of labor force)
    # World Bank does not publish policy/bond yield series -- IR/LTY/FX/STOCK
    # are not available here by design; those rely on central banks / yfinance.
}


class WorldBankAdapter(SourceAdapter):
    name = "worldbank"

    def fetch(self, *, country_iso3: str, indicator_type: str, start_date: str, end_date: str) -> list[ObservationPoint]:
        indicator = _INDICATOR_MAP.get(indicator_type)
        if not indicator:
            raise SourceUnavailableError(f"World Bank has no indicator mapped for {indicator_type}")

        start_year = start_date[:4]
        end_year = end_date[:4]
        url = BASE_URL.format(iso3=country_iso3, indicator=indicator)
        params = {
            "format": "json",
            "date": f"{start_year}:{end_year}",
            "per_page": 1000,
        }

        try:
            resp = retrying_get(url, params=params)
            payload = resp.json()
        except Exception as e:
            raise SourceFetchError(f"World Bank request failed for {indicator}/{country_iso3}: {e}") from e

        if not isinstance(payload, list) or len(payload) < 2 or payload[1] is None:
            return []

        points: list[ObservationPoint] = []
        for row in payload[1]:
            year = row.get("date")
            raw_value = row.get("value")
            if year is None or raw_value is None:
                continue
            try:
                points.append(ObservationPoint(date=f"{year}-01-01", value=float(raw_value)))
            except ValueError:
                continue

        return self._clean_and_sort(points)
