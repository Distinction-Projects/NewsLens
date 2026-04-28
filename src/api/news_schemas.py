from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict


class NewsMeta(BaseModel):
    source_url: str | None = None
    source_mode: str | None = None
    snapshot_date: str | None = None
    etag: str | None = None
    schema_version: str | None = None
    contract: str | None = None
    generated_at: str | None = None
    digest_generated_at: str | None = None
    digest_run_id: str | None = None
    fetched_at: str | None = None
    ttl_seconds: int | None = None
    from_cache: bool | None = None
    using_last_good: bool | None = None
    fetch_error: str | None = None
    input_articles_count: int | None = None
    excluded_unscraped_articles: int | None = None
    filtered_count: int | None = None
    returned_count: int | None = None
    model_config = ConfigDict(extra="allow")


class NewsArticle(BaseModel):
    id: str | None = None
    title: str | None = None
    link: str | None = None
    published: str | None = None
    published_at: str | None = None
    summary: str | None = None
    ai_summary: str | None = None
    ai_tags: list[str] | None = None
    topic_tags: list[str] | None = None
    tags: list[str] | None = None
    source: dict[str, Any] | None = None
    source_name: str | None = None
    feed: dict[str, Any] | None = None
    scraped: dict[str, Any] | None = None
    scrape_error: str | None = None
    score: dict[str, Any] | None = None
    model_config = ConfigDict(extra="allow")


class NewsStatsData(BaseModel):
    derived: dict[str, Any]
    summary: dict[str, Any] = {}
    analysis: dict[str, Any] = {}
    model_config = ConfigDict(extra="allow")


class NewsUpstreamData(BaseModel):
    upstream: Any | None = None
    model_config = ConfigDict(extra="allow")


class NewsApiEnvelope(BaseModel):
    status: str
    meta: NewsMeta | dict[str, Any] | None = None
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


class NewsDigestEnvelope(NewsApiEnvelope):
    data: list[NewsArticle] | None = None


class NewsLatestDigestEnvelope(NewsApiEnvelope):
    data: NewsArticle | None = None


class NewsStatsEnvelope(NewsApiEnvelope):
    data: NewsStatsData | None = None


class NewsUpstreamEnvelope(NewsApiEnvelope):
    data: NewsUpstreamData | None = None


class NewsExportEnvelope(NewsApiEnvelope):
    artifact: str | None = None
    format: str | None = None
    rows: list[dict[str, Any]] | None = None


class NewsFreshnessEnvelope(NewsApiEnvelope):
    is_fresh: bool | None = None
    reason: str | None = None
    generated_at: str | None = None
    age_seconds: int | None = None
    max_age_seconds: int | None = None
