"""
Every upstream data source (central bank, IMF, World Bank, Yahoo Finance...)
implements the same tiny interface: given a series identifier and a date
range, return a clean, sorted list of {date, value} points or raise.

This is deliberately narrow. Adapters own all the messy parsing/quirks of
their upstream API; the ingestion pipeline and the FastAPI routes never see
that mess -- they only see ObservationPoint lists or a clear exception.
"""
from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass

import requests
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from app.core.config import settings

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ObservationPoint:
    date: str   # "YYYY-MM-DD"
    value: float


class SourceUnavailableError(RuntimeError):
    """Raised when a source has no data for this series (not necessarily an
    error -- e.g. a country simply has no series mapped for this adapter)."""


class SourceFetchError(RuntimeError):
    """Raised when the upstream call itself failed (network, auth, parsing)."""


def retrying_get(url: str, **kwargs) -> requests.Response:
    """Shared HTTP GET with retry/backoff, used by every adapter so a single
    transient timeout doesn't silently degrade to an empty series."""

    @retry(
        reraise=True,
        stop=stop_after_attempt(settings.max_retries),
        wait=wait_exponential(multiplier=settings.retry_backoff_seconds, min=1, max=20),
        retry=retry_if_exception_type((requests.ConnectionError, requests.Timeout)),
    )
    def _get() -> requests.Response:
        resp = requests.get(url, timeout=settings.request_timeout_seconds, **kwargs)
        resp.raise_for_status()
        return resp

    return _get()


class SourceAdapter(ABC):
    """One adapter per upstream data source."""

    #: short machine-readable name stored in series_metadata.source
    name: str = "base"

    @abstractmethod
    def fetch(
        self,
        *,
        country_iso3: str,
        indicator_type: str,
        start_date: str,
        end_date: str,
    ) -> list[ObservationPoint]:
        """Return sorted, deduped observations for this indicator/country in
        [start_date, end_date]. Raise SourceUnavailableError if this adapter
        simply doesn't cover this indicator/country combination (not an
        error -- the pipeline will move to the next source in the chain).
        Raise SourceFetchError for a genuine upstream failure."""
        raise NotImplementedError

    @staticmethod
    def _clean_and_sort(points: list[ObservationPoint]) -> list[ObservationPoint]:
        dedup: dict[str, float] = {}
        for p in points:
            dedup[p.date] = p.value
        return [ObservationPoint(date=d, value=v) for d, v in sorted(dedup.items())]
