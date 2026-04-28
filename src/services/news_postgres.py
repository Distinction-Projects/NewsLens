from __future__ import annotations

import os
from datetime import date, datetime, timezone
from typing import Any

from src.services.database import _connect_kwargs, _import_psycopg, database_url
from src.services.rss_digest import (
    RssDigestNotFoundError,
    RssDigestUpstreamError,
    parse_snapshot_date,
    sort_records_desc,
)


def _as_iso_utc(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        dt_value = value
    else:
        try:
            dt_value = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        except Exception:
            return str(value)
    if dt_value.tzinfo is None:
        dt_value = dt_value.replace(tzinfo=timezone.utc)
    return dt_value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _coerce_int(value: Any, default: int) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return default
    return parsed if parsed > 0 else default


def _json_value(value: Any) -> Any:
    if hasattr(value, "obj"):
        return value.obj
    return value


def _date_value(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date().isoformat()
    if isinstance(value, date):
        return value.isoformat()
    return str(value)


class PostgresNewsClient:
    """Read the canonical news bundle from the normalized Postgres schema.

    The public controller expects the same shape produced by RssDigestClient.
    Keeping that boundary stable lets the API switch storage backends without
    rewriting filtering, export, or route behavior.
    """

    def __init__(self, ttl_seconds: int | None = None) -> None:
        self.ttl_seconds = _coerce_int(ttl_seconds if ttl_seconds is not None else os.getenv("NEWS_DB_CACHE_TTL_SECONDS"), 300)
        self.max_age_seconds = _coerce_int(os.getenv("RSS_MAX_AGE_SECONDS"), 36 * 3600)

    def _connect(self):
        url = database_url()
        if not url:
            raise RssDigestUpstreamError("DATABASE_URL or SUPABASE_DIRECT_DB_URL is required for postgres news backend")

        psycopg = _import_psycopg()
        if psycopg is None:
            raise RssDigestUpstreamError("psycopg is not installed")

        return psycopg.connect(url, **_connect_kwargs(url))

    def get_payload(self, *, force_refresh: bool = False, snapshot_date: str | None = None) -> dict[str, Any]:
        del force_refresh
        parsed_snapshot = parse_snapshot_date(snapshot_date)
        source_mode = "snapshot" if parsed_snapshot else "current"

        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT
                        id, source_mode, snapshot_date, source_url, schema_version, contract,
                        generated_at, digest_generated_at, digest_run_id, created_at,
                        article_count, score_count
                    FROM public.import_runs
                    WHERE status = 'completed'
                      AND source_mode = %s
                      AND snapshot_date IS NOT DISTINCT FROM %s
                    ORDER BY created_at DESC
                    LIMIT 1;
                    """,
                    (source_mode, parsed_snapshot),
                )
                import_row = cur.fetchone()
                if not import_row:
                    label = f"snapshot {parsed_snapshot}" if parsed_snapshot else "current import"
                    raise RssDigestNotFoundError(f"No completed Postgres news import found for {label}")

                import_run_id = str(import_row[0])
                cur.execute(
                    """
                    SELECT raw_payload
                    FROM public.articles
                    WHERE last_seen_import_run_id = %s
                    ORDER BY published_at DESC NULLS LAST, updated_at DESC, id ASC;
                    """,
                    (import_run_id,),
                )
                articles = [_json_value(row[0]) for row in cur.fetchall()]

                cur.execute(
                    """
                    SELECT payload
                    FROM public.derived_metrics
                    WHERE snapshot_key = %s
                      AND metric_key = 'news_stats'
                    ORDER BY created_at DESC
                    LIMIT 1;
                    """,
                    (parsed_snapshot or "current",),
                )
                stats_row = cur.fetchone()
                stats = _json_value(stats_row[0]) if stats_row else {}

        ordered_articles = sort_records_desc([article for article in articles if isinstance(article, dict)])
        generated_at = _as_iso_utc(import_row[6])
        fetched_at = _as_iso_utc(import_row[9])
        return {
            "upstream_payload": {
                "source": "postgres",
                "import_run_id": import_run_id,
                "items": ordered_articles,
                "derived": stats if isinstance(stats, dict) else {},
            },
            "articles_normalized": ordered_articles,
            "stats": stats if isinstance(stats, dict) else {},
            "input_articles_count": import_row[10] if import_row[10] is not None else len(ordered_articles),
            "excluded_unscraped_articles": 0,
            "generated_at": generated_at,
            "generated_at_dt": import_row[6],
            "schema_version": import_row[4],
            "contract": import_row[5],
            "digest_generated_at": _as_iso_utc(import_row[7]),
            "digest_run_id": import_row[8],
            "summary": {},
            "analysis": {},
            "fetched_at": fetched_at,
            "source_url": import_row[3],
            "source_mode": import_row[1],
            "snapshot_date": _date_value(import_row[2]),
            "ttl_seconds": self.ttl_seconds,
            "from_cache": False,
            "using_last_good": False,
            "error": None,
            "etag": None,
        }
