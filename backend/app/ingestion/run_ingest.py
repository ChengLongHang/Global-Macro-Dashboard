"""
Cron entrypoint. Examples:

    # Full backfill (20y history), run once on setup or weekly:
    python -m app.ingestion.run_ingest --mode full

    # Cheap incremental refresh (last 7 days), safe to run hourly/daily:
    python -m app.ingestion.run_ingest --mode incremental --lookback-days 3

Suggested crontab (see backend/CRON_SETUP.md for details):

    # Daily incremental refresh at 02:00
    0 2 * * * cd /path/to/backend && /path/to/venv/bin/python -m app.ingestion.run_ingest --mode incremental

    # Weekly full backfill on Sundays at 03:00
    0 3 * * 0 cd /path/to/backend && /path/to/venv/bin/python -m app.ingestion.run_ingest --mode full
"""
import argparse
import json
import sys

from app.core.logging_config import configure_logging
from app.db.session import init_db
from app.ingestion.pipeline import run_full_ingest, run_incremental_ingest


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the macro data ingestion pipeline")
    parser.add_argument("--mode", choices=["full", "incremental"], default="incremental")
    parser.add_argument("--history-years", type=int, default=20, help="Only used with --mode full")
    parser.add_argument("--lookback-days", type=int, default=7, help="Only used with --mode incremental")
    args = parser.parse_args()

    configure_logging()
    init_db()

    if args.mode == "full":
        summary = run_full_ingest(history_years=args.history_years)
    else:
        summary = run_incremental_ingest(lookback_days=args.lookback_days)

    print(json.dumps({k: v for k, v in summary.items() if k != "series"}, indent=2))
    return 1 if summary["error"] > 0 and summary["success"] == 0 else 0


if __name__ == "__main__":
    sys.exit(main())
