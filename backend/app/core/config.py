"""
Centralized configuration. All secrets/config come from environment variables
(loaded from a .env file via python-dotenv). Nothing below should be hardcoded
in adapters or routes -- import `settings` instead.
"""
from functools import lru_cache
from pathlib import Path
from typing import List

from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent.parent.parent  # backend/


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # ---------------- Database ----------------
    database_url: str = f"sqlite:///{BASE_DIR / 'macro_globe.db'}"

    # ---------------- CORS ----------------
    cors_origins: List[str] = ["http://localhost:5173", "http://localhost:3000"]

    # ---------------- Source API keys ----------------
    # Required / already available per the project owner:
    fred_api_key: str | None = None
    banxico_api_token: str | None = None

    # Free-to-register keys needed for full G20 central-bank coverage:
    ecos_api_key: str | None = None       # Bank of Korea ECOS
    evds_api_key: str | None = None       # CBRT (Turkey) EVDS

    # No key required (public REST APIs), listed for completeness / future use:
    #   - ECB Statistical Data Warehouse (SDW)      -> no key
    #   - Bank of Canada Valet API                  -> no key
    #   - BCB SGS (Brazil)                          -> no key
    #   - World Bank API                            -> no key
    #   - IMF (imfp / direct SDMX)                  -> no key
    #   - Yahoo Finance (yfinance)                  -> no key

    # ---------------- Cache / ingestion ----------------
    request_timeout_seconds: int = 30
    max_retries: int = 3
    retry_backoff_seconds: float = 2.0

    log_level: str = "INFO"


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
