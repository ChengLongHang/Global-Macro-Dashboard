import logging
from datetime import datetime, timedelta

from app.db.crud import record_ingestion_result, upsert_series_metadata
from app.db.session import get_session
from app.registry import all_series, get_source_chain
from app.sources import ADAPTERS
from app.sources.base import SourceFetchError, SourceUnavailableError

logger = logging.getLogger(__name__)

# How far back to backfill on first ingest / full refresh.
DEFAULT_HISTORY_YEARS = 20


def run_full_ingest(history_years: int = DEFAULT_HISTORY_YEARS) -> dict:
    """Refresh every series in the registry. Intended to be invoked by cron
    (see run_ingest.py) on a schedule -- NOT called from API request paths.
    Returns a summary dict suitable for logging/alerting."""
    end_date = datetime.utcnow().date()
    start_date = end_date - timedelta(days=365 * history_years)
    start_str, end_str = start_date.isoformat(), end_date.isoformat()

    summary = {"success": 0, "empty": 0, "error": 0, "series": []}

    for series in all_series():
        result = _ingest_one_series(series, start_str, end_str)
        summary[result["status"]] += 1
        summary["series"].append(result)

    logger.info(
        f"Ingestion complete: {summary['success']} succeeded, "
        f"{summary['empty']} empty, {summary['error']} errored "
        f"(of {len(summary['series'])} total series)"
    )
    return summary


def run_incremental_ingest(lookback_days: int = 7) -> dict:
    """Cheaper refresh for frequent cron runs -- only pulls the last N days,
    relying on the upsert-on-conflict write path so re-fetching recent
    history is idempotent and safe to run often (e.g. hourly for FX/stocks)."""
    end_date = datetime.utcnow().date()
    start_date = end_date - timedelta(days=lookback_days)
    start_str, end_str = start_date.isoformat(), end_date.isoformat()

    summary = {"success": 0, "empty": 0, "error": 0, "series": []}
    for series in all_series():
        result = _ingest_one_series(series, start_str, end_str)
        summary[result["status"]] += 1
        summary["series"].append(result)
    return summary


def _ingest_one_series(series: dict, start_date: str, end_date: str) -> dict:
    series_key = series["series_key"]
    country_id = series["country_id"]
    indicator_type = series["indicator_type"]
    chain = get_source_chain(country_id, indicator_type)

    with get_session() as session:
        upsert_series_metadata(
            session,
            series_key=series_key,
            country_id=country_id,
            indicator_type=indicator_type,
            name=series["name"],
            category=series["category"],
        )

    last_error = None
    for source_name in chain:
        adapter = ADAPTERS.get(source_name)
        if adapter is None:
            logger.warning(f"Unknown adapter '{source_name}' referenced in registry for {series_key}")
            continue
        try:
            points = adapter.fetch(
                country_iso3=country_id,
                indicator_type=indicator_type,
                start_date=start_date,
                end_date=end_date,
            )
        except SourceUnavailableError:
            continue  # this adapter just doesn't cover this series; try next
        except SourceFetchError as e:
            last_error = str(e)
            logger.warning(f"{series_key}: {source_name} failed ({e}); trying next source")
            continue
        except Exception as e:  # belt-and-braces: never let one bad series kill the run
            last_error = f"unexpected error from {source_name}: {e}"
            logger.exception(f"{series_key}: unexpected error from {source_name}")
            continue

        if points:
            with get_session() as session:
                record_ingestion_result(
                    session, series_key=series_key, source=source_name, points=points, error=None
                )
            return {"series_key": series_key, "status": "success", "source": source_name, "rows": len(points)}
        # empty result from this adapter -- fall through to next source

    # Every source in the chain either didn't cover this series or returned nothing
    with get_session() as session:
        record_ingestion_result(
            session, series_key=series_key, source=None, points=[], error=last_error
        )
    status = "error" if last_error else "empty"
    return {"series_key": series_key, "status": status, "source": None, "rows": 0, "error": last_error}
