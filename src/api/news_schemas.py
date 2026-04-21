from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict


class NewsApiEnvelope(BaseModel):
    status: str
    meta: dict[str, Any] | None = None
    filters: dict[str, Any] | None = None
    data: Any | None = None
    error: str | None = None
    artifact: str | None = None
    format: str | None = None
    rows: list[dict[str, Any]] | None = None
    is_fresh: bool | None = None
    reason: str | None = None
    generated_at: str | None = None
    age_seconds: int | None = None
    max_age_seconds: int | None = None
    model_config = ConfigDict(extra="allow")

