from pydantic import BaseModel


class CountryOut(BaseModel):
    id: str
    name: str
    lat: float
    lng: float


class IndicatorOut(BaseModel):
    id: str
    name: str
    category: str
    source: str


class DataPoint(BaseModel):
    date: str
    value: float


class PipelineStatusRow(BaseModel):
    series_key: str
    country_id: str
    indicator_type: str
    name: str
    source: str | None
    row_count: int
    last_refreshed_at: str | None
    last_success_at: str | None
    last_error: str | None
