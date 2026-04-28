from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from typing import Any

from src.services.database import _connect_kwargs, _import_psycopg, database_url
from src.services.rss_digest import RssDigestClient, parse_snapshot_date


def _slug(value: Any, fallback: str) -> str:
    text = str(value or "").strip().lower()
    text = re.sub(r"[^a-z0-9]+", "-", text).strip("-")
    return text or fallback


def _hash_id(prefix: str, value: Any) -> str:
    digest = hashlib.sha1(str(value or "").encode("utf-8")).hexdigest()[:16]
    return f"{prefix}-{digest}"


def _json(value: Any):
    psycopg = _import_psycopg()
    return psycopg.types.json.Jsonb(value if value is not None else {})


def _parse_datetime(value: Any) -> datetime | None:
    if not value:
        return None
    text = str(value).strip()
    if not text:
        return None
    try:
        parsed = parsedate_to_datetime(text)
    except Exception:
        parsed = None
    if parsed is None:
        try:
            parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
        except Exception:
            return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _source_identity(article: dict[str, Any]) -> tuple[str, str, dict[str, Any]]:
    source = article.get("source") if isinstance(article.get("source"), dict) else {}
    feed = article.get("feed") if isinstance(article.get("feed"), dict) else {}
    name = str(source.get("name") or feed.get("name") or "Unknown Source").strip()
    source_id = str(source.get("id") or "").strip() or _slug(name, "unknown-source")
    return source_id, name, source


def _feed_identity(article: dict[str, Any], source_id: str) -> tuple[str, dict[str, Any]]:
    feed = article.get("feed") if isinstance(article.get("feed"), dict) else {}
    feed_url = feed.get("url") or feed.get("link") or feed.get("name") or source_id
    return _hash_id("feed", f"{source_id}:{feed_url}"), feed


def _article_tags(article: dict[str, Any]) -> list[tuple[str, str]]:
    rows: list[tuple[str, str]] = []
    for tag_type, key in (("ai", "ai_tags"), ("topic", "topic_tags")):
        tags = article.get(key)
        if not isinstance(tags, list):
            continue
        for tag in tags:
            text = str(tag or "").strip()
            if text:
                rows.append((tag_type, text))
    return rows


def _lens_score_rows(article: dict[str, Any]) -> list[tuple[str, dict[str, Any]]]:
    score = article.get("score") if isinstance(article.get("score"), dict) else {}
    lens_scores = score.get("lens_scores") if isinstance(score.get("lens_scores"), dict) else {}
    rows: list[tuple[str, dict[str, Any]]] = []
    for lens_name, payload in lens_scores.items():
        if isinstance(payload, dict):
            rows.append((str(lens_name), payload))
    if not rows and score:
        rows.append(("Overall Score", score))
    return rows


def _score_value(payload: dict[str, Any], *keys: str) -> float | None:
    for key in keys:
        value = payload.get(key)
        if isinstance(value, (int, float)):
            return float(value)
        try:
            if value is not None:
                return float(value)
        except Exception:
            continue
    return None


def _upsert_article(cur, *, article: dict[str, Any], import_run_id: str | None, first_seen: bool) -> int:
    article_id = str(article.get("id") or article.get("link") or "").strip()
    if not article_id:
        return 0

    source_id, source_name, source_payload = _source_identity(article)
    feed_id, feed_payload = _feed_identity(article, source_id)
    score = article.get("score") if isinstance(article.get("score"), dict) else {}
    published_at = _parse_datetime(article.get("published") or article.get("published_at"))
    scrape_error = article.get("scrape_error")
    scraped_ok = not bool(scrape_error) and article.get("scraped") is not None

    cur.execute(
        """
        INSERT INTO public.sources (id, name, metadata, updated_at)
        VALUES (%s, %s, %s::jsonb, NOW())
        ON CONFLICT (id) DO UPDATE
        SET name = EXCLUDED.name,
            metadata = EXCLUDED.metadata,
            updated_at = NOW();
        """,
        (source_id, source_name, _json(source_payload)),
    )
    cur.execute(
        """
        INSERT INTO public.feeds (id, source_id, name, url, metadata, updated_at)
        VALUES (%s, %s, %s, %s, %s::jsonb, NOW())
        ON CONFLICT (id) DO UPDATE
        SET source_id = EXCLUDED.source_id,
            name = EXCLUDED.name,
            url = EXCLUDED.url,
            metadata = EXCLUDED.metadata,
            updated_at = NOW();
        """,
        (feed_id, source_id, feed_payload.get("name"), feed_payload.get("url"), _json(feed_payload)),
    )
    cur.execute(
        """
        INSERT INTO public.articles (
            id, source_id, feed_id, title, link, published_at, summary, ai_summary,
            scrape_error, scraped_ok, score_value, score_max_value, score_percent, rubric_count,
            raw_payload, first_seen_import_run_id, last_seen_import_run_id, updated_at
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb, %s, %s, NOW())
        ON CONFLICT (id) DO UPDATE
        SET source_id = EXCLUDED.source_id,
            feed_id = EXCLUDED.feed_id,
            title = EXCLUDED.title,
            link = EXCLUDED.link,
            published_at = EXCLUDED.published_at,
            summary = EXCLUDED.summary,
            ai_summary = EXCLUDED.ai_summary,
            scrape_error = EXCLUDED.scrape_error,
            scraped_ok = EXCLUDED.scraped_ok,
            score_value = EXCLUDED.score_value,
            score_max_value = EXCLUDED.score_max_value,
            score_percent = EXCLUDED.score_percent,
            rubric_count = EXCLUDED.rubric_count,
            raw_payload = EXCLUDED.raw_payload,
            first_seen_import_run_id = COALESCE(public.articles.first_seen_import_run_id, EXCLUDED.first_seen_import_run_id),
            last_seen_import_run_id = EXCLUDED.last_seen_import_run_id,
            updated_at = NOW();
        """,
        (
            article_id,
            source_id,
            feed_id,
            article.get("title"),
            article.get("link"),
            published_at,
            article.get("summary"),
            article.get("ai_summary"),
            scrape_error,
            scraped_ok,
            _score_value(score, "value", "score_value"),
            _score_value(score, "max_value", "score_max_value"),
            _score_value(score, "percent", "score_percent"),
            score.get("rubric_count"),
            _json(article),
            import_run_id if first_seen else None,
            import_run_id,
        ),
    )

    cur.execute("DELETE FROM public.article_tags WHERE article_id = %s;", (article_id,))
    for tag_type, tag in _article_tags(article):
        cur.execute(
            """
            INSERT INTO public.article_tags (article_id, tag_type, tag, tag_normalized)
            VALUES (%s, %s, %s, %s)
            ON CONFLICT (article_id, tag_type, tag_normalized) DO UPDATE
            SET tag = EXCLUDED.tag;
            """,
            (article_id, tag_type, tag, tag.strip().lower()),
        )

    score_count = 0
    for lens_name, payload in _lens_score_rows(article):
        lens_id = _slug(lens_name, "overall-score")
        rubric_id = f"aggregate:{lens_id}"
        rubric_signature = f"aggregate:{lens_id}"
        cur.execute(
            """
            INSERT INTO public.lenses (id, name, metadata, updated_at)
            VALUES (%s, %s, '{}'::jsonb, NOW())
            ON CONFLICT (id) DO UPDATE SET name = EXCLUDED.name, updated_at = NOW();
            """,
            (lens_id, lens_name),
        )
        cur.execute(
            """
            INSERT INTO public.rubrics (id, lens_id, name, signature, raw_payload, updated_at)
            VALUES (%s, %s, %s, %s, '{}'::jsonb, NOW())
            ON CONFLICT (id) DO UPDATE
            SET lens_id = EXCLUDED.lens_id,
                name = EXCLUDED.name,
                signature = EXCLUDED.signature,
                updated_at = NOW();
            """,
            (rubric_id, lens_id, "Aggregate score", rubric_signature),
        )
        cur.execute(
            """
            INSERT INTO public.article_scores (
                article_id, lens_id, rubric_id, score_value, score_max_value, score_percent, raw_payload, updated_at
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s::jsonb, NOW())
            ON CONFLICT (article_id, lens_id, rubric_id) DO UPDATE
            SET score_value = EXCLUDED.score_value,
                score_max_value = EXCLUDED.score_max_value,
                score_percent = EXCLUDED.score_percent,
                raw_payload = EXCLUDED.raw_payload,
                updated_at = NOW();
            """,
            (
                article_id,
                lens_id,
                rubric_id,
                _score_value(payload, "value", "score", "raw_score"),
                _score_value(payload, "max_value", "max_score"),
                _score_value(payload, "percent", "normalized_percent"),
                _json(payload),
            ),
        )
        score_count += 1
    return score_count


def import_current(*, snapshot_date: str | None = None, dry_run: bool = False) -> dict[str, Any]:
    parsed_snapshot = parse_snapshot_date(snapshot_date)
    bundle = RssDigestClient().get_payload(force_refresh=True, snapshot_date=parsed_snapshot)
    articles = bundle.get("articles_normalized") if isinstance(bundle.get("articles_normalized"), list) else []
    stats = bundle.get("stats") if isinstance(bundle.get("stats"), dict) else {}

    if dry_run:
        return {
            "status": "dry_run",
            "source_mode": bundle.get("source_mode"),
            "snapshot_date": parsed_snapshot,
            "article_count": len(articles),
            "has_stats": bool(stats),
        }

    url = database_url()
    if not url:
        raise RuntimeError("DATABASE_URL or SUPABASE_DIRECT_DB_URL is required for import.")
    psycopg = _import_psycopg()
    if psycopg is None:
        raise RuntimeError("psycopg is not installed.")

    source_mode = "snapshot" if parsed_snapshot else "current"
    with psycopg.connect(url, **_connect_kwargs(url)) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO public.import_runs (
                    source_mode, snapshot_date, source_url, schema_version, contract,
                    generated_at, digest_generated_at, digest_run_id, status, metadata
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, 'running', %s::jsonb)
                RETURNING id;
                """,
                (
                    source_mode,
                    parsed_snapshot,
                    bundle.get("source_url"),
                    bundle.get("schema_version"),
                    bundle.get("contract"),
                    _parse_datetime(bundle.get("generated_at")),
                    _parse_datetime(bundle.get("digest_generated_at")),
                    bundle.get("digest_run_id"),
                    _json({"source_mode": bundle.get("source_mode"), "fetched_at": bundle.get("fetched_at")}),
                ),
            )
            import_run_id = str(cur.fetchone()[0])
            score_count = 0
            for article in articles:
                if isinstance(article, dict):
                    score_count += _upsert_article(cur, article=article, import_run_id=import_run_id, first_seen=True)

            cur.execute(
                """
                INSERT INTO public.derived_metrics (import_run_id, snapshot_key, snapshot_date, metric_key, payload)
                VALUES (%s, %s, %s, 'news_stats', %s::jsonb)
                ON CONFLICT (snapshot_key, metric_key) DO UPDATE
                SET import_run_id = EXCLUDED.import_run_id,
                    snapshot_date = EXCLUDED.snapshot_date,
                    payload = EXCLUDED.payload,
                    created_at = NOW();
                """,
                (import_run_id, parsed_snapshot or "current", parsed_snapshot, _json(stats)),
            )

            if parsed_snapshot:
                cur.execute(
                    """
                    INSERT INTO public.snapshots (
                        snapshot_date, import_run_id, source_url, generated_at, article_count, metadata, updated_at
                    )
                    VALUES (%s, %s, %s, %s, %s, %s::jsonb, NOW())
                    ON CONFLICT (snapshot_date) DO UPDATE
                    SET import_run_id = EXCLUDED.import_run_id,
                        source_url = EXCLUDED.source_url,
                        generated_at = EXCLUDED.generated_at,
                        article_count = EXCLUDED.article_count,
                        metadata = EXCLUDED.metadata,
                        updated_at = NOW();
                    """,
                    (
                        parsed_snapshot,
                        import_run_id,
                        bundle.get("source_url"),
                        _parse_datetime(bundle.get("generated_at")),
                        len(articles),
                        _json({"schema_version": bundle.get("schema_version"), "contract": bundle.get("contract")}),
                    ),
                )

            cur.execute(
                """
                UPDATE public.import_runs
                SET status = 'completed',
                    article_count = %s,
                    score_count = %s
                WHERE id = %s;
                """,
                (len(articles), score_count, import_run_id),
            )
        conn.commit()

    return {
        "status": "completed",
        "import_run_id": import_run_id,
        "source_mode": source_mode,
        "snapshot_date": parsed_snapshot,
        "article_count": len(articles),
        "score_count": score_count,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Import the RSS contract into Postgres.")
    parser.add_argument("--source", choices=["current"], default="current")
    parser.add_argument("--snapshot-date", default=None, help="Optional YYYY-MM-DD snapshot date.")
    parser.add_argument("--refresh-derived", action="store_true", help="Accepted for CLI compatibility; derived stats are always stored.")
    parser.add_argument("--dry-run", action="store_true", help="Load and summarize without writing to Postgres.")
    args = parser.parse_args(argv)

    try:
        result = import_current(snapshot_date=args.snapshot_date, dry_run=args.dry_run)
    except Exception as exc:
        print(json.dumps({"status": "error", "error": str(exc)}, sort_keys=True))
        return 1
    print(json.dumps(result, sort_keys=True, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
