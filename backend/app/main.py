from datetime import datetime, timedelta

from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.logging_config import configure_logging
from app.db.crud import get_observations, get_pipeline_status
from app.db.session import get_session_dep, init_db
from app.registry import COUNTRIES, get_indicators_for_country, series_key
from app.schemas import CountryOut, DataPoint, IndicatorOut, PipelineStatusRow

configure_logging()

app = FastAPI(title="Macro Globe API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def on_startup() -> None:
    init_db()


@app.get("/")
def root():
    return {"message": "Macro Globe API is running!"}


@app.get("/api/health")
def health_check():
    return {"status": "healthy"}


@app.get("/api/countries", response_model=list[CountryOut])
def get_countries():
    return COUNTRIES


@app.get("/api/indicators/{country_id}", response_model=list[IndicatorOut])
def get_country_indicators(country_id: str):
    if country_id not in {c["id"] for c in COUNTRIES}:
        raise HTTPException(status_code=404, detail=f"Unknown country_id: {country_id}")
    return get_indicators_for_country(country_id)


@app.get("/api/theme_indicators/{country_id}", response_model=list[IndicatorOut])
def get_theme_indicators(country_id: str, theme: str):
    all_indicators = get_indicators_for_country(country_id)
    return [ind for ind in all_indicators if ind["category"] == theme]


@app.get("/api/data", response_model=list[DataPoint])
def fetch_data(
    series_id: str = Query(..., description="Indicator series ID, e.g. CPI_BRA"),
    country_id: str = Query(..., description="Country ID, e.g. BRA"),
    start_date: str = Query("2004-01-01", description="Start date YYYY-MM-DD"),
    end_date: str | None = Query(None, description="End date YYYY-MM-DD"),
    session: Session = Depends(get_session_dep),
):
    """Reads exclusively from the local database -- populated by the
    ingestion pipeline on its own schedule (see app/ingestion). This route
    never calls FRED/IMF/central banks directly, so it stays fast and never
    trips upstream rate limits no matter how many users hit it."""
    if end_date is None:
        end_date = datetime.utcnow().date().isoformat()

    result = get_observations(session, series_id, start_date, end_date)
    if not result:
        raise HTTPException(
            status_code=404,
            detail=(
                f"No cached data for {series_id} in {country_id} between {start_date} and {end_date}. "
                "The ingestion pipeline may not have run yet, or this source/country combination "
                "has no coverage -- check /api/pipeline/status."
            ),
        )
    return result


@app.get("/api/pipeline/status", response_model=list[PipelineStatusRow])
def pipeline_status(
    stale_only: bool = Query(False, description="Only show series not refreshed in the last 48h"),
    session: Session = Depends(get_session_dep),
):
    """Observability endpoint: shows every tracked series, which source last
    served it, row counts, and any error -- so pipeline health is visible
    without grepping cron logs."""
    rows = get_pipeline_status(session)
    if not stale_only:
        return rows

    cutoff = datetime.utcnow() - timedelta(hours=48)
    return [
        r for r in rows
        if r["last_refreshed_at"] is None or datetime.fromisoformat(r["last_refreshed_at"]) < cutoff
    ]


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
