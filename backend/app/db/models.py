from datetime import datetime

from sqlalchemy import (
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import declarative_base

Base = declarative_base()


class SeriesMetadata(Base):
    """One row per logical series, e.g. 'CPI_BRA'. Tracks which source last
    served it successfully and when, so the API and a status dashboard can
    reason about data freshness without touching upstream sources."""

    __tablename__ = "series_metadata"

    series_key = Column(String, primary_key=True)          # e.g. "CPI_BRA"
    country_id = Column(String, index=True, nullable=False)
    indicator_type = Column(String, index=True, nullable=False)  # CPI, GDP, UNEMP, IR, LTY, FX, STOCK
    name = Column(String, nullable=False)
    category = Column(String, nullable=False)
    unit = Column(String, nullable=True)
    source = Column(String, nullable=True)                 # adapter that last succeeded
    last_refreshed_at = Column(DateTime, nullable=True)     # last time we attempted
    last_success_at = Column(DateTime, nullable=True)       # last time we got data
    last_error = Column(String, nullable=True)
    row_count = Column(Integer, default=0)


class Observation(Base):
    __tablename__ = "observations"

    id = Column(Integer, primary_key=True, autoincrement=True)
    series_key = Column(String, ForeignKey("series_metadata.series_key"), index=True, nullable=False)
    date = Column(String, index=True, nullable=False)  # ISO "YYYY-MM-DD"
    value = Column(Float, nullable=False)

    __table_args__ = (
        UniqueConstraint("series_key", "date", name="uq_series_date"),
    )


class IngestionRun(Base):
    """Append-only audit log of every ingestion attempt, so pipeline health
    can be inspected via /api/pipeline/status instead of grepping logs."""

    __tablename__ = "ingestion_runs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    series_key = Column(String, index=True, nullable=False)
    source = Column(String, nullable=True)
    status = Column(String, nullable=False)   # success | empty | error
    rows_written = Column(Integer, default=0)
    started_at = Column(DateTime, default=datetime.utcnow)
    finished_at = Column(DateTime, nullable=True)
    error = Column(String, nullable=True)
