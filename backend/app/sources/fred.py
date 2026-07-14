import logging

import pandas as pd

from app.core.config import settings
from app.sources.base import (
    ObservationPoint,
    SourceAdapter,
    SourceFetchError,
    SourceUnavailableError,
    retrying_get,
)

logger = logging.getLogger(__name__)

# FRED series IDs we know are good for USA. International series exist on
# FRED too (mirrored from OECD/BIS) but are inconsistent in coverage, so we
# only rely on FRED as the primary source for the US and treat it as a
# central-bank-grade source there.
_USA_SERIES = {
    "IR": "DGS2",       # 2Y Treasury yield
    "LTY": "DGS10",      # 10Y Treasury yield
    "CPI": "CPIAUCSL",
    "GDP": "GDPC1",
    "UNEMP": "UNRATE",
}


class FredAdapter(SourceAdapter):
    name = "fred"

    def fetch(self, *, country_iso3: str, indicator_type: str, start_date: str, end_date: str) -> list[ObservationPoint]:
        if country_iso3 != "USA":
            raise SourceUnavailableError("FRED adapter only covers USA in this build")

        series_id = _USA_SERIES.get(indicator_type)
        if not series_id:
            raise SourceUnavailableError(f"No FRED series mapped for indicator {indicator_type}")

        if not settings.fred_api_key:
            raise SourceFetchError("FRED_API_KEY is not configured")

        url = "https://api.stlouisfed.org/fred/series/observations"
        params = {
            "series_id": series_id,
            "api_key": settings.fred_api_key,
            "file_type": "json",
            "observation_start": start_date,
            "observation_end": end_date,
            "sort_order": "asc",
        }
        try:
            resp = retrying_get(url, params=params)
            obs = resp.json().get("observations", [])
        except Exception as e:
            raise SourceFetchError(f"FRED request failed for {series_id}: {e}") from e

        df = pd.DataFrame(obs)
        if df.empty:
            return []

        df["date"] = pd.to_datetime(df["date"], errors="coerce")
        df["value"] = pd.to_numeric(df["value"].replace(".", pd.NA), errors="coerce")
        df = df.dropna(subset=["date", "value"])

        points = [ObservationPoint(date=r.date.strftime("%Y-%m-%d"), value=float(r.value)) for r in df.itertuples(index=False)]
        return self._clean_and_sort(points)
