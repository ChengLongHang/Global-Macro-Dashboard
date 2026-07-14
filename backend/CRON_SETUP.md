# Scheduling the ingestion pipeline

The API (`app/main.py`) never calls upstream sources directly -- it only
reads from the local database. A separate process has to populate that
database. That's `app/ingestion/run_ingest.py`.

## One-time setup

```bash
cd backend
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # fill in FRED_API_KEY / BANXICO_API_TOKEN (already have),
                        # ECOS_API_KEY / EVDS_API_KEY (optional, see .env.example)

# Full 20-year backfill for every country/indicator -- run this once now.
python -m app.ingestion.run_ingest --mode full
```

This will take a while the first time (dozens of series, each with retry/backoff
on failure) -- that's expected and is the point: it only has to happen rarely.

## Recurring schedule (cron)

Add to crontab (`crontab -e`):

```cron
# Cheap incremental refresh (last 7 days of each series) once a day at 02:00.
# Safe to run daily even for monthly/annual series -- upserts are idempotent.
0 2 * * * cd /path/to/backend && /path/to/venv/bin/python -m app.ingestion.run_ingest --mode incremental >> /var/log/macro_globe_ingest.log 2>&1

# Full re-backfill weekly (Sundays 03:00) to catch upstream revisions to
# historical data (e.g. GDP gets revised months after first release).
0 3 * * 0 cd /path/to/backend && /path/to/venv/bin/python -m app.ingestion.run_ingest --mode full >> /var/log/macro_globe_ingest.log 2>&1
```

If FX/stock intraday freshness matters more than this, add a third,
more frequent job restricted to those indicator types -- not implemented
yet, but `run_incremental_ingest` in `app/ingestion/pipeline.py` is the
place to add a `indicator_types` filter if you want that.

## Checking pipeline health

```bash
curl http://localhost:8000/api/pipeline/status | jq
curl "http://localhost:8000/api/pipeline/status?stale_only=true" | jq
```

Each row shows which source last served that series, when it last
succeeded, and the last error if it's currently failing -- so a broken
adapter (e.g. an upstream API that changed its schema) is visible without
digging through logs.
