import logging

from app.sources.base import ObservationPoint, SourceAdapter, SourceFetchError, SourceUnavailableError, retrying_get

logger = logging.getLogger(__name__)

# Bank of Canada Valet API. Public, no key required.
# Docs: https://www.bankofcanada.ca/valet/docs
BASE_URL = "https://www.bankofcanada.ca/valet/observations"

_SERIES_MAP = {
    "IR": "V39079",     # Bank rate (Overnight target proxy)
    "LTY": "V39055",    # Government of Canada 10Y benchmark bond yield
    "CPI": "V41690973",  # CPI, all-items
    # GDP / unemployment are Statistics Canada series, not published as
    # Bank of Canada Valet series -- left for the World Bank/IMF fallback.
}


class BocAdapter(SourceAdapter):
    name = "boc"

    def fetch(self, *, country_iso3: str, indicator_type: str, start_date: str, end_date: str) -> list[ObservationPoint]:
        if country_iso3 != "CAN":
            raise SourceUnavailableError("Bank of Canada adapter only covers CAN")

        series_id = _SERIES_MAP.get(indicator_type)
        if not series_id:
            raise SourceUnavailableError(f"No Bank of Canada series mapped for indicator {indicator_type}")

        url = f"{BASE_URL}/{series_id}/json"
        params = {"start_date": start_date, "end_date": end_date}

        try:
            resp = retrying_get(url, params=params)
            payload = resp.json()
        except Exception as e:
            raise SourceFetchError(f"Bank of Canada request failed for {series_id}: {e}") from e

        points: list[ObservationPoint] = []
        for row in payload.get("observations", []):
            date = row.get("d")
            cell = row.get(series_id, {})
            raw_value = cell.get("v") if isinstance(cell, dict) else None
            if date is None or raw_value is None:
                continue
            try:
                points.append(ObservationPoint(date=date, value=float(raw_value)))
            except ValueError:
                continue

        return self._clean_and_sort(points)
