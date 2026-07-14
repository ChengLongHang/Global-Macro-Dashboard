import logging

from app.core.config import settings
from app.sources.base import ObservationPoint, SourceAdapter, SourceFetchError, SourceUnavailableError, retrying_get

logger = logging.getLogger(__name__)

# Banco de Mexico - Sistema de Informacion Economica (SIE) API.
# Requires a free token (BANXICO_API_TOKEN), already available per project owner.
# Docs: https://www.banxico.org.mx/SieAPIRest/service/v1/
BASE_URL = "https://www.banxico.org.mx/SieAPIRest/service/v1/series/{series_id}/datos/{start}/{end}"

_SERIES_MAP = {
    "IR": "SF43783",     # Target overnight interbank rate
    "CPI": "SP1",         # National Consumer Price Index
    # GDP / long-term yield / unemployment: not all published as clean SIE
    # series -- fall back to World Bank/IMF for those.
}


class BanxicoAdapter(SourceAdapter):
    name = "banxico"

    def fetch(self, *, country_iso3: str, indicator_type: str, start_date: str, end_date: str) -> list[ObservationPoint]:
        if country_iso3 != "MEX":
            raise SourceUnavailableError("Banxico adapter only covers MEX")

        series_id = _SERIES_MAP.get(indicator_type)
        if not series_id:
            raise SourceUnavailableError(f"No Banxico series mapped for indicator {indicator_type}")

        if not settings.banxico_api_token:
            raise SourceFetchError("BANXICO_API_TOKEN is not configured")

        url = BASE_URL.format(series_id=series_id, start=start_date, end=end_date)
        headers = {"Bmx-Token": settings.banxico_api_token, "Accept": "application/json"}

        try:
            resp = retrying_get(url, headers=headers)
            payload = resp.json()
        except Exception as e:
            raise SourceFetchError(f"Banxico request failed for {series_id}: {e}") from e

        points: list[ObservationPoint] = []
        try:
            series = payload["bmx"]["series"][0]
            for row in series.get("datos", []):
                date_mx = row.get("fecha")   # "DD/MM/YYYY"
                raw_value = row.get("dato")
                if not date_mx or raw_value in (None, "N/E"):
                    continue
                d, m, y = date_mx.split("/")
                points.append(ObservationPoint(date=f"{y}-{m}-{d}", value=float(raw_value)))
        except (KeyError, IndexError, ValueError) as e:
            raise SourceFetchError(f"Could not parse Banxico response for {series_id}: {e}") from e

        return self._clean_and_sort(points)
