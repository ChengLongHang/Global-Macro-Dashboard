import logging

from app.core.config import settings
from app.sources.base import ObservationPoint, SourceAdapter, SourceFetchError, SourceUnavailableError, retrying_get

logger = logging.getLogger(__name__)

# Bank of Korea Economic Statistics System (ECOS) API.
# Requires a free API key (ECOS_API_KEY) -- register at https://ecos.bok.or.kr
BASE_URL = "https://ecos.bok.or.kr/api/StatisticSearch/{key}/json/en/1/10000/{stat_code}/{period}/{start}/{end}/{item_code}"

# (stat_code, period, item_code) per indicator. period: "M" monthly, "A" annual, "D" daily.
_SERIES_MAP = {
    "IR": ("722Y001", "M", "0101000"),   # Base rate
    "CPI": ("901Y009", "M", "0"),         # Consumer price index, total
    "UNEMP": ("901Y027", "M", "I61BC"),   # Unemployment rate
    "GDP": ("200Y001", "A", "10111"),     # Real GDP (annual)
}


class EcosAdapter(SourceAdapter):
    name = "ecos"

    def fetch(self, *, country_iso3: str, indicator_type: str, start_date: str, end_date: str) -> list[ObservationPoint]:
        if country_iso3 != "KOR":
            raise SourceUnavailableError("ECOS adapter only covers KOR")

        mapping = _SERIES_MAP.get(indicator_type)
        if not mapping:
            raise SourceUnavailableError(f"No ECOS series mapped for indicator {indicator_type}")

        if not settings.ecos_api_key:
            raise SourceFetchError("ECOS_API_KEY is not configured")

        stat_code, period, item_code = mapping
        start = self._format_period(start_date, period)
        end = self._format_period(end_date, period)

        url = BASE_URL.format(
            key=settings.ecos_api_key,
            stat_code=stat_code,
            period=period,
            start=start,
            end=end,
            item_code=item_code,
        )

        try:
            resp = retrying_get(url)
            payload = resp.json()
        except Exception as e:
            raise SourceFetchError(f"ECOS request failed for {stat_code}: {e}") from e

        if "RESULT" in payload:
            # ECOS returns an error envelope like {"RESULT": {"CODE": ..., "MESSAGE": ...}}
            raise SourceFetchError(f"ECOS error for {stat_code}: {payload['RESULT'].get('MESSAGE')}")

        rows = payload.get("StatisticSearch", {}).get("row", [])
        points: list[ObservationPoint] = []
        for row in rows:
            time_str = row.get("TIME")
            raw_value = row.get("DATA_VALUE")
            if not time_str or raw_value is None:
                continue
            date = self._period_to_date(time_str, period)
            try:
                points.append(ObservationPoint(date=date, value=float(raw_value)))
            except ValueError:
                continue

        return self._clean_and_sort(points)

    @staticmethod
    def _format_period(iso_date: str, period: str) -> str:
        y, m, _ = iso_date.split("-")
        if period == "A":
            return y
        if period == "M":
            return f"{y}{m}"
        return iso_date.replace("-", "")

    @staticmethod
    def _period_to_date(time_str: str, period: str) -> str:
        if period == "A":
            return f"{time_str}-01-01"
        if period == "M":
            return f"{time_str[:4]}-{time_str[4:6]}-01"
        return f"{time_str[:4]}-{time_str[4:6]}-{time_str[6:8]}"
