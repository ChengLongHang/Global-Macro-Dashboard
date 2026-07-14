import logging

import pandas as pd
import yfinance as yf

from app.sources.base import ObservationPoint, SourceAdapter, SourceFetchError, SourceUnavailableError

logger = logging.getLogger(__name__)

_FX_TICKERS = {
    "USA": "EURUSD=X", "GBR": "GBPUSD=X", "DEU": "EURUSD=X", "FRA": "EURUSD=X",
    "ITA": "EURUSD=X", "ESP": "EURUSD=X", "MEX": "MXNUSD=X", "CAN": "CADUSD=X",
    "AUS": "AUDUSD=X", "JPN": "JPY=X", "CHN": "CNY=X", "IND": "INRUSD=X",
    "BRA": "BRLUSD=X", "KOR": "KRW=X", "TUR": "TRYUSD=X", "ZAF": "ZARUSD=X",
    "RUS": "RUBUSD=X", "IDN": "IDRUSD=X", "SAU": "SARUSD=X", "ARG": "ARSUSD=X",
}

_STOCK_TICKERS = {
    "USA": "^GSPC", "GBR": "^FTSE", "DEU": "^GDAXI", "JPN": "^N225",
    "CHN": "000001.SS", "IND": "^BSESN", "BRA": "^BVSP", "CAN": "^GSPTSE",
    "AUS": "^AXJO", "FRA": "^FCHI", "ITA": "FTMIB.MI", "ESP": "^IBEX",
    "MEX": "^MXX", "KOR": "^KS11", "TUR": "XU100.IS", "ZAF": "^JN0U.JO",
    "IDN": "^JKSE", "SAU": "^TASI.SR", "ARG": "^MERV",
}


class YFinanceAdapter(SourceAdapter):
    name = "yfinance"

    def fetch(self, *, country_iso3: str, indicator_type: str, start_date: str, end_date: str) -> list[ObservationPoint]:
        if indicator_type == "FX":
            ticker = _FX_TICKERS.get(country_iso3)
        elif indicator_type == "STOCK":
            ticker = _STOCK_TICKERS.get(country_iso3)
        else:
            raise SourceUnavailableError("yfinance only serves FX and STOCK indicators")

        if not ticker:
            raise SourceUnavailableError(f"No yfinance ticker mapped for {indicator_type}/{country_iso3}")

        try:
            df = yf.download(
                ticker, start=start_date, end=end_date, progress=False,
                auto_adjust=False, group_by="column", threads=False,
            )
        except Exception as e:
            raise SourceFetchError(f"yfinance download failed for {ticker}: {e}") from e

        if df is None or df.empty:
            return []

        if isinstance(df.columns, pd.MultiIndex):
            if ("Close", ticker) in df.columns:
                close = df[("Close", ticker)]
            elif "Close" in df.columns.get_level_values(0):
                close = df.xs("Close", axis=1, level=0)
                close = close.iloc[:, 0] if isinstance(close, pd.DataFrame) else close
            else:
                return []
        else:
            if "Close" not in df.columns:
                return []
            close = df["Close"]

        if isinstance(close, pd.DataFrame):
            close = close.iloc[:, 0]

        close = pd.to_numeric(close, errors="coerce").dropna()
        points = [
            ObservationPoint(date=idx.strftime("%Y-%m-%d"), value=float(val))
            for idx, val in close.items() if pd.notna(val)
        ]
        return self._clean_and_sort(points)
