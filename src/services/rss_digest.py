from __future__ import annotations

import json
import os
import threading
import time
from collections import Counter
from datetime import date, datetime, timezone
from email.utils import parsedate_to_datetime
from typing import Any
from urllib.error import HTTPError
from urllib.request import Request, urlopen


DEFAULT_RSS_DAILY_JSON_URL = (
    "https://raw.githubusercontent.com/Distinction-Projects/RSS_Feeds/main/data/processed/rss_openai_precomputed.json"
)

RECORD_LIST_KEYS = (
    "digests",
    "items",
    "articles",
    "records",
    "entries",
    "results",
    "data",
)

TIMESTAMP_KEYS = (
    "generated_at",
    "generatedAt",
    "published_at",
    "publishedAt",
    "updated_at",
    "updatedAt",
    "created_at",
    "createdAt",
    "published",
    "date",
    "published_date",
    "publishedDate",
    "timestamp",
)

TAG_KEYS = ("tags", "tag", "topics", "topic", "keywords")
SOURCE_KEYS = ("source", "source_name", "sourceName", "publisher", "feed", "domain")


def _coerce_int(value: Any, default: int, minimum: int = 1) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return default
    return max(parsed, minimum)


def _as_iso_utc(value: datetime | None) -> str | None:
    if value is None:
        return None
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _coerce_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def parse_datetime(value: Any) -> datetime | None:
    if value is None:
        return None

    if isinstance(value, datetime):
        dt_value = value
    elif isinstance(value, (int, float)):
        try:
            dt_value = datetime.fromtimestamp(float(value), tz=timezone.utc)
        except (OverflowError, OSError, ValueError):
            return None
    else:
        raw = str(value).strip()
        if not raw:
            return None
        try:
            parsed_rfc2822 = parsedate_to_datetime(raw)
            if parsed_rfc2822 is not None:
                dt_value = parsed_rfc2822
            else:
                raise ValueError("not an RFC-2822 timestamp")
        except (TypeError, ValueError):
            raw = raw.replace("Z", "+00:00")
            try:
                dt_value = datetime.fromisoformat(raw)
            except ValueError:
                try:
                    parsed_date = datetime.strptime(raw, "%Y-%m-%d")
                    dt_value = parsed_date.replace(tzinfo=timezone.utc)
                except ValueError:
                    return None

    if dt_value.tzinfo is None:
        dt_value = dt_value.replace(tzinfo=timezone.utc)
    return dt_value.astimezone(timezone.utc)


def _clean_text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def extract_records(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        return [row for row in payload if isinstance(row, dict)]

    if not isinstance(payload, dict):
        return []

    for key in RECORD_LIST_KEYS:
        value = payload.get(key)
        if isinstance(value, list):
            return [row for row in value if isinstance(row, dict)]

    list_values = [value for value in payload.values() if isinstance(value, list)]
    if len(list_values) == 1:
        return [row for row in list_values[0] if isinstance(row, dict)]

    if any(key in payload for key in TIMESTAMP_KEYS + TAG_KEYS + SOURCE_KEYS):
        return [payload]

    return []


def _record_datetime(record: dict[str, Any]) -> datetime | None:
    for key in TIMESTAMP_KEYS:
        parsed = parse_datetime(record.get(key))
        if parsed is not None:
            return parsed
    return None


def extract_generated_at(payload: Any) -> datetime | None:
    if not isinstance(payload, dict):
        return None
    for key in ("generated_at", "generatedAt"):
        parsed = parse_datetime(payload.get(key))
        if parsed is not None:
            return parsed
    return None


def _values_to_strings(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [piece.strip() for piece in value.split(",") if piece.strip()]
    if isinstance(value, list):
        collected: list[str] = []
        for item in value:
            collected.extend(_values_to_strings(item))
        return collected
    coerced = str(value).strip()
    return [coerced] if coerced else []


def _unique_case_insensitive(values: list[str]) -> list[str]:
    seen: set[str] = set()
    unique: list[str] = []
    for value in values:
        stripped = value.strip()
        if not stripped:
            continue
        lowered = stripped.lower()
        if lowered in seen:
            continue
        seen.add(lowered)
        unique.append(stripped)
    return unique


def normalize_article(article: dict[str, Any]) -> dict[str, Any]:
    source = article.get("source")
    source_obj = source if isinstance(source, dict) else {}

    feed = article.get("feed")
    feed_obj = feed if isinstance(feed, dict) else {}

    ai_tags = _unique_case_insensitive(_values_to_strings(article.get("ai_tags")))
    topic_tags = _unique_case_insensitive(_values_to_strings(article.get("topic_tags")))
    all_tags = _unique_case_insensitive(ai_tags + topic_tags)

    published_value = article.get("published")
    published_dt = parse_datetime(published_value)
    published_at = _as_iso_utc(published_dt)

    score = article.get("score")
    score_obj = score if isinstance(score, dict) else {}
    score_value = _coerce_float(score_obj.get("value"))
    score_max_value = _coerce_float(score_obj.get("max_value"))
    score_percent = _coerce_float(score_obj.get("percent"))
    if score_percent is None and score_value is not None and score_max_value and score_max_value > 0:
        score_percent = (score_value / score_max_value) * 100

    rubric_count_raw = score_obj.get("rubric_count")
    try:
        rubric_count = int(rubric_count_raw) if rubric_count_raw is not None else None
    except (TypeError, ValueError):
        rubric_count = None

    high_score = article.get("high_score")
    high_score_obj = high_score if isinstance(high_score, dict) else None

    normalized = {
        "id": _clean_text(article.get("id")),
        "title": _clean_text(article.get("title")),
        "link": _clean_text(article.get("link")),
        "published": _clean_text(published_value),
        "published_at": published_at,
        "summary": _clean_text(article.get("summary")),
        "ai_summary": _clean_text(article.get("ai_summary")),
        "ai_tags": ai_tags,
        "topic_tags": topic_tags,
        "tags": all_tags,
        "source": {
            "id": _clean_text(source_obj.get("id")),
            "name": _clean_text(source_obj.get("name")),
        },
        "feed": {
            "name": _clean_text(feed_obj.get("name")),
            "url": _clean_text(feed_obj.get("url")),
        },
        "score": {
            "value": score_value,
            "max_value": score_max_value,
            "percent": score_percent,
            "rubric_count": rubric_count,
        },
        "high_score": high_score_obj,
        "scraped": article.get("scraped"),
        "scrape_error": article.get("scrape_error"),
        "audit": article.get("audit"),
    }

    return normalized


def normalize_articles(payload: Any) -> list[dict[str, Any]]:
    records = extract_records(payload)
    return [normalize_article(record) for record in records]


def _tag_values_for_record(record: dict[str, Any]) -> list[str]:
    tags = _values_to_strings(record.get("tags"))
    if tags:
        return _unique_case_insensitive(tags)
    derived = _values_to_strings(record.get("ai_tags")) + _values_to_strings(record.get("topic_tags"))
    return _unique_case_insensitive(derived)


def _source_values_for_record(record: dict[str, Any]) -> list[str]:
    sources: list[str] = []
    source = record.get("source")
    if isinstance(source, dict):
        sources.extend(_values_to_strings(source.get("id")))
        sources.extend(_values_to_strings(source.get("name")))

    feed = record.get("feed")
    if isinstance(feed, dict):
        sources.extend(_values_to_strings(feed.get("name")))

    for key in SOURCE_KEYS:
        sources.extend(_values_to_strings(record.get(key)))
    return _unique_case_insensitive(sources)


def _record_matches_date(record: dict[str, Any], target_date: date) -> bool:
    parsed = _record_datetime(record)
    return parsed is not None and parsed.date() == target_date


def _record_matches_tag(record: dict[str, Any], target_tag_lower: str) -> bool:
    tags = _tag_values_for_record(record)
    return any(tag.lower() == target_tag_lower for tag in tags)


def _record_matches_source(record: dict[str, Any], target_source_lower: str) -> bool:
    sources = _source_values_for_record(record)
    return any(target_source_lower in source.lower() for source in sources)


def filter_records(
    records: list[dict[str, Any]],
    date_filter: str | None = None,
    tag_filter: str | None = None,
    source_filter: str | None = None,
) -> list[dict[str, Any]]:
    target_date: date | None = None
    if date_filter:
        date_raw = date_filter.strip()
        try:
            target_date = datetime.strptime(date_raw, "%Y-%m-%d").date()
        except ValueError as exc:
            raise ValueError("date must be YYYY-MM-DD") from exc

    target_tag_lower = tag_filter.strip().lower() if tag_filter else None
    target_source_lower = source_filter.strip().lower() if source_filter else None

    filtered: list[dict[str, Any]] = []
    for record in records:
        if target_date and not _record_matches_date(record, target_date):
            continue
        if target_tag_lower and not _record_matches_tag(record, target_tag_lower):
            continue
        if target_source_lower and not _record_matches_source(record, target_source_lower):
            continue
        filtered.append(record)
    return filtered


def sort_records_desc(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    epoch = datetime.fromtimestamp(0, tz=timezone.utc)
    return sorted(records, key=lambda row: _record_datetime(row) or epoch, reverse=True)


def derive_stats(records: list[dict[str, Any]], payload: Any) -> dict[str, Any]:
    source_counter: Counter[str] = Counter()
    tag_counter: Counter[str] = Counter()
    daily_counter: Counter[str] = Counter()

    score_percents: list[float] = []
    scored_articles = 0
    high_scoring_articles = 0

    for record in records:
        source = record.get("source")
        source_name = None
        if isinstance(source, dict):
            source_name = source.get("name") or source.get("id")
        source_label = _clean_text(source_name) or "Unknown"
        source_counter[source_label] += 1

        unique_tags = {tag.strip() for tag in _tag_values_for_record(record) if tag.strip()}
        for tag in unique_tags:
            tag_counter[tag] += 1

        published_dt = _record_datetime(record)
        if published_dt is not None:
            daily_counter[published_dt.date().isoformat()] += 1

        score = record.get("score")
        score_obj = score if isinstance(score, dict) else {}
        max_value = _coerce_float(score_obj.get("max_value"))
        value = _coerce_float(score_obj.get("value"))
        percent = _coerce_float(score_obj.get("percent"))

        if max_value is not None and max_value > 0:
            scored_articles += 1

        if percent is None and value is not None and max_value and max_value > 0:
            percent = (value / max_value) * 100

        if percent is not None:
            score_percents.append(percent)

        high_score = record.get("high_score")
        if isinstance(high_score, dict):
            high_scoring_articles += 1

    score_bins = [
        {"label": "0-20", "min": 0, "max": 20, "count": 0},
        {"label": "20-40", "min": 20, "max": 40, "count": 0},
        {"label": "40-60", "min": 40, "max": 60, "count": 0},
        {"label": "60-80", "min": 60, "max": 80, "count": 0},
        {"label": "80-100", "min": 80, "max": 100, "count": 0},
    ]
    for score_percent in score_percents:
        bounded = min(max(score_percent, 0.0), 100.0)
        if bounded < 20:
            score_bins[0]["count"] += 1
        elif bounded < 40:
            score_bins[1]["count"] += 1
        elif bounded < 60:
            score_bins[2]["count"] += 1
        elif bounded < 80:
            score_bins[3]["count"] += 1
        else:
            score_bins[4]["count"] += 1

    source_counts = [{"source": source, "count": count} for source, count in source_counter.most_common()]
    tag_counts = [{"tag": tag, "count": count} for tag, count in tag_counter.most_common()]
    daily_counts = [{"date": day, "count": daily_counter[day]} for day in sorted(daily_counter.keys())]

    summary = payload.get("summary") if isinstance(payload, dict) else None
    analysis = payload.get("analysis") if isinstance(payload, dict) else None

    total_articles = len(records)
    average_percent = sum(score_percents) / len(score_percents) if score_percents else None
    high_score_ratio = (high_scoring_articles / total_articles) if total_articles else 0.0

    return {
        "total_articles": total_articles,
        "scored_articles": scored_articles,
        "high_scoring_articles": high_scoring_articles,
        "high_score_ratio": high_score_ratio,
        "source_counts": source_counts,
        "tag_counts": tag_counts,
        "daily_counts_utc": daily_counts,
        "score_distribution": {
            "bins": score_bins,
            "average_percent": average_percent,
            "min_percent": min(score_percents) if score_percents else None,
            "max_percent": max(score_percents) if score_percents else None,
            "count": len(score_percents),
        },
        "upstream_summary": summary if isinstance(summary, dict) else {},
        "upstream_analysis": analysis if isinstance(analysis, dict) else {},
    }


class RssDigestClient:
    def __init__(
        self,
        source_url: str | None = None,
        ttl_seconds: int | None = None,
        timeout_seconds: int | None = None,
    ) -> None:
        self.source_url = (
            source_url
            or os.getenv("RSS_DAILY_JSON_URL")
            or DEFAULT_RSS_DAILY_JSON_URL
        ).strip()
        self.ttl_seconds = _coerce_int(
            ttl_seconds if ttl_seconds is not None else os.getenv("RSS_CACHE_TTL_SECONDS"),
            default=86400,
        )
        self.timeout_seconds = _coerce_int(
            timeout_seconds if timeout_seconds is not None else os.getenv("RSS_HTTP_TIMEOUT_SECONDS"),
            default=20,
        )
        self.max_age_seconds = _coerce_int(os.getenv("RSS_MAX_AGE_SECONDS"), default=36 * 3600)

        self._lock = threading.Lock()
        self._cache_bundle: dict[str, Any] | None = None
        self._cache_fetched_at: datetime | None = None
        self._cache_until_epoch: float = 0.0
        self._cache_is_last_good = False
        self._last_fetch_error: str | None = None

        self._last_good_bundle: dict[str, Any] | None = None
        self._last_good_fetched_at: datetime | None = None

        self._etag: str | None = None

    def _fetch_json(self) -> tuple[Any | None, str | None, bool]:
        if not self.source_url:
            raise RuntimeError("RSS_DAILY_JSON_URL is not set")

        headers = {
            "Accept": "application/json",
            "User-Agent": "ml-sentiment-rss-consumer/1.0",
        }
        if self._etag:
            headers["If-None-Match"] = self._etag

        request = Request(
            self.source_url,
            headers=headers,
        )
        try:
            with urlopen(request, timeout=self.timeout_seconds) as response:
                content = response.read().decode("utf-8")
                etag = response.headers.get("ETag")
            return json.loads(content), etag, False
        except HTTPError as exc:
            if exc.code == 304:
                return None, self._etag, True
            raise

    def _build_bundle_from_payload(self, payload: Any) -> dict[str, Any]:
        generated_at = extract_generated_at(payload)
        digest = payload.get("digest") if isinstance(payload, dict) else None
        digest_obj = digest if isinstance(digest, dict) else {}
        digest_generated_at = parse_datetime(digest_obj.get("generated_at"))

        records = normalize_articles(payload)
        ordered_records = sort_records_desc(records)
        stats = derive_stats(ordered_records, payload)

        return {
            "payload": payload,
            "articles_normalized": ordered_records,
            "stats": stats,
            "generated_at": _as_iso_utc(generated_at),
            "generated_at_dt": generated_at,
            "schema_version": payload.get("schema_version") if isinstance(payload, dict) else None,
            "contract": payload.get("contract") if isinstance(payload, dict) else None,
            "digest_generated_at": _as_iso_utc(digest_generated_at),
            "digest_run_id": digest_obj.get("run_id"),
            "summary": payload.get("summary") if isinstance(payload, dict) and isinstance(payload.get("summary"), dict) else {},
            "analysis": payload.get("analysis") if isinstance(payload, dict) and isinstance(payload.get("analysis"), dict) else {},
        }

    def _format_bundle(
        self,
        bundle: dict[str, Any],
        fetched_at: datetime | None,
        from_cache: bool,
        using_last_good: bool,
        error: str | None,
    ) -> dict[str, Any]:
        return {
            **bundle,
            "fetched_at": _as_iso_utc(fetched_at),
            "source_url": self.source_url,
            "ttl_seconds": self.ttl_seconds,
            "from_cache": from_cache,
            "using_last_good": using_last_good,
            "error": error,
            "etag": self._etag,
        }

    def get_payload(self, force_refresh: bool = False) -> dict[str, Any]:
        now_epoch = time.time()
        with self._lock:
            cache_valid = self._cache_bundle is not None and now_epoch < self._cache_until_epoch
            if cache_valid and not force_refresh:
                return self._format_bundle(
                    bundle=self._cache_bundle,
                    fetched_at=self._cache_fetched_at,
                    from_cache=True,
                    using_last_good=self._cache_is_last_good,
                    error=self._last_fetch_error,
                )

            try:
                payload, etag, not_modified = self._fetch_json()
                fetched_at = datetime.now(timezone.utc)
                if etag:
                    self._etag = etag

                if not_modified:
                    if self._cache_bundle is not None:
                        bundle = self._cache_bundle
                    elif self._last_good_bundle is not None:
                        bundle = self._last_good_bundle
                    else:
                        raise RuntimeError("Received 304 but no cached payload is available")
                else:
                    bundle = self._build_bundle_from_payload(payload)

                self._cache_bundle = bundle
                self._cache_fetched_at = fetched_at
                self._cache_until_epoch = now_epoch + self.ttl_seconds
                self._cache_is_last_good = False
                self._last_fetch_error = None

                self._last_good_bundle = bundle
                self._last_good_fetched_at = fetched_at

                return self._format_bundle(
                    bundle=bundle,
                    fetched_at=fetched_at,
                    from_cache=False,
                    using_last_good=False,
                    error=None,
                )
            except Exception as exc:  # noqa: BLE001
                if self._last_good_bundle is None:
                    raise

                self._last_fetch_error = f"{type(exc).__name__}: {exc}"
                self._cache_bundle = self._last_good_bundle
                self._cache_fetched_at = self._last_good_fetched_at
                self._cache_until_epoch = now_epoch + self.ttl_seconds
                self._cache_is_last_good = True

                return self._format_bundle(
                    bundle=self._last_good_bundle,
                    fetched_at=self._last_good_fetched_at,
                    from_cache=False,
                    using_last_good=True,
                    error=self._last_fetch_error,
                )
