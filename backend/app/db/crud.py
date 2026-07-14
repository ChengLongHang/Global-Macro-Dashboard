from datetime import datetime
from typing import Sequence

from sqlalchemy import delete
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.orm import Session

from app.db.models import IngestionRun, Observation, SeriesMetadata
from app.sources.base import ObservationPoint


def upsert_series_metadata(
    session: Session,
    *,
    series_key: str,
    country_id: str,
    indicator_type: str,
    name: str,
    category: str,
    unit: str | None = None,
) -> SeriesMetadata:
    row = session.get(SeriesMetadata, series_key)
    if row is None:
        row = SeriesMetadata(
            series_key=series_key,
            country_id=country_id,
            indicator_type=indicator_type,
            name=name,
            category=category,
            unit=unit,
        )
        session.add(row)
    else:
        row.country_id = country_id
        row.indicator_type = indicator_type
        row.name = name
        row.category = category
        row.unit = unit
    return row


def record_ingestion_result(
    session: Session,
    *,
    series_key: str,
    source: str | None,
    points: Sequence[ObservationPoint],
    error: str | None,
) -> None:
    """Upsert observations (if any) and update series metadata + run log in
    one place, so every adapter call goes through the same bookkeeping."""
    now = datetime.utcnow()
    meta = session.get(SeriesMetadata, series_key)
    status = "error" if error else ("success" if points else "empty")

    if points:
        # Bulk upsert -- SQLite ON CONFLICT DO UPDATE, avoids read-then-write races
        rows = [{"series_key": series_key, "date": p.date, "value": p.value} for p in points]
        stmt = sqlite_insert(Observation).values(rows)
        stmt = stmt.on_conflict_do_update(
            index_elements=["series_key", "date"],
            set_={"value": stmt.excluded.value},
        )
        session.execute(stmt)

    if meta is not None:
        meta.last_refreshed_at = now
        if points:
            meta.last_success_at = now
            meta.source = source
            meta.row_count = session.query(Observation).filter_by(series_key=series_key).count() + len(points)
        meta.last_error = error

    session.add(
        IngestionRun(
            series_key=series_key,
            source=source,
            status=status,
            rows_written=len(points),
            started_at=now,
            finished_at=datetime.utcnow(),
            error=error,
        )
    )


def get_observations(
    session: Session,
    series_key: str,
    start_date: str,
    end_date: str,
) -> list[dict]:
    rows = (
        session.query(Observation)
        .filter(
            Observation.series_key == series_key,
            Observation.date >= start_date,
            Observation.date <= end_date,
        )
        .order_by(Observation.date.asc())
        .all()
    )
    return [{"date": r.date, "value": r.value} for r in rows]


def get_pipeline_status(session: Session) -> list[dict]:
    rows = session.query(SeriesMetadata).order_by(SeriesMetadata.series_key.asc()).all()
    return [
        {
            "series_key": r.series_key,
            "country_id": r.country_id,
            "indicator_type": r.indicator_type,
            "name": r.name,
            "source": r.source,
            "row_count": r.row_count,
            "last_refreshed_at": r.last_refreshed_at.isoformat() if r.last_refreshed_at else None,
            "last_success_at": r.last_success_at.isoformat() if r.last_success_at else None,
            "last_error": r.last_error,
        }
        for r in rows
    ]


def clear_series(session: Session, series_key: str) -> None:
    session.execute(delete(Observation).where(Observation.series_key == series_key))
