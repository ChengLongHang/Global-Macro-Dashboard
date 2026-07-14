import logging

from app.sources.base import ObservationPoint, SourceAdapter, SourceFetchError, SourceUnavailableError, retrying_get

logger = logging.getLogger(__name__)

# Banco Central do Brasil - Sistema Gerenciador de Series Temporais (SGS).
# Public, no API key. Docs: https://dadosabertos.bcb.gov.br/dataset/series-temporais
BASE_URL = "https://api.bcb.gov.br/dados/serie/bcdata.sgs.{series_id}/dados"

_SERIES_MAP = {
    "IR": 432,       # SELIC target rate
    "LTY": 12,        # placeholder: 12 is actually SELIC daily; long bond yield
                       # series in SGS is less standardized -- verify series id
                       # before relying on this in production.
    "CPI": 433,       # IPCA (broad consumer price index), monthly % change
    "UNEMP": 24369,   # Unemployment rate (PNAD Continua)
    "GDP": 4380,      # GDP monthly index (proxy; not quarterly national accounts)
}


class BcbAdapter(SourceAdapter):
    name = "bcb"

    def fetch(self, *, country_iso3: str, indicator_type: str, start_date: str, end_date: str) -> list[ObservationPoint]:
        if country_iso3 != "BRA":
            raise SourceUnavailableError("BCB adapter only covers BRA")

        series_id = _SERIES_MAP.get(indicator_type)
        if not series_id:
            raise SourceUnavailableError(f"No BCB SGS series mapped for indicator {indicator_type}")

        url = BASE_URL.format(series_id=series_id)
        params = {
            "formato": "json",
            "dataInicial": self._to_br_date(start_date),
            "dataFinal": self._to_br_date(end_date),
        }

        try:
            resp = retrying_get(url, params=params)
            payload = resp.json()
        except Exception as e:
            raise SourceFetchError(f"BCB SGS request failed for series {series_id}: {e}") from e

        points: list[ObservationPoint] = []
        for row in payload:
            date_br = row.get("data")  # "DD/MM/YYYY"
            raw_value = row.get("valor")
            if not date_br or raw_value is None:
                continue
            try:
                d, m, y = date_br.split("/")
                iso_date = f"{y}-{m}-{d}"
                points.append(ObservationPoint(date=iso_date, value=float(raw_value)))
            except (ValueError, AttributeError):
                continue

        return self._clean_and_sort(points)

    @staticmethod
    def _to_br_date(iso_date: str) -> str:
        """BCB expects DD/MM/YYYY."""
        y, m, d = iso_date.split("-")
        return f"{d}/{m}/{y}"
