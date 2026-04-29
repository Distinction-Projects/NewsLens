from __future__ import annotations

import json
import math
import os
import random
import statistics
import threading
import time
from collections import Counter, OrderedDict, defaultdict
from datetime import date, datetime, timezone
from email.utils import parsedate_to_datetime
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from src.analytics.news_event_control import build_event_clusters, event_embedding_config_from_env

try:
    import numpy as np
except Exception:  # pragma: no cover - optional dependency guard
    np = None


DEFAULT_RSS_DAILY_JSON_URL = (
    "https://raw.githubusercontent.com/Distinction-Projects/RSS_Feeds/main/data/processed/rss_openai_precomputed.json"
)
DEFAULT_RSS_HISTORY_JSON_URL_TEMPLATE = (
    "https://raw.githubusercontent.com/Distinction-Projects/RSS_Feeds/main/data/history/rss_openai_daily_{date}.json"
)
CONFIG_PLACEHOLDER_VALUES = {"", "-", "none", "null", "unset", "changeme"}

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


class RssDigestError(RuntimeError):
    pass


class RssDigestNotFoundError(RssDigestError):
    pass


class RssDigestUpstreamError(RssDigestError):
    pass


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


def _normalize_score_lens_scores(value: Any) -> dict[str, dict[str, float | int | None]]:
    if not isinstance(value, dict):
        return {}

    normalized: dict[str, dict[str, float | int | None]] = {}
    for lens_name, payload in value.items():
        if not isinstance(lens_name, str) or not isinstance(payload, dict):
            continue

        value_score = _coerce_float(payload.get("value"))
        max_value = _coerce_float(payload.get("max_value"))
        percent = _coerce_float(payload.get("percent"))
        if percent is None and value_score is not None and max_value and max_value > 0:
            percent = (value_score / max_value) * 100.0

        rubric_count_raw = payload.get("rubric_count")
        try:
            rubric_count = int(rubric_count_raw) if rubric_count_raw is not None else None
        except (TypeError, ValueError):
            rubric_count = None

        normalized[lens_name] = {
            "value": value_score,
            "max_value": max_value,
            "percent": percent,
            "rubric_count": rubric_count,
        }
    return normalized


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


def parse_snapshot_date(value: Any) -> str | None:
    if value is None:
        return None
    raw = str(value).strip()
    if not raw:
        return None
    try:
        parsed = datetime.strptime(raw, "%Y-%m-%d").date()
    except ValueError as exc:
        raise ValueError("snapshot_date must be YYYY-MM-DD") from exc
    return parsed.isoformat()


def _clean_text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _clean_config_url(value: Any) -> str | None:
    text = _clean_text(value)
    if text is None:
        return None
    if text.lower() in CONFIG_PLACEHOLDER_VALUES:
        return None
    return text


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


def _scrape_succeeded(article: dict[str, Any]) -> bool:
    scrape_error = _clean_text(article.get("scrape_error"))
    if scrape_error:
        return False

    # Legacy payloads may not include scrape fields; keep them eligible.
    if "scraped" not in article:
        return True

    scraped = article.get("scraped")
    return isinstance(scraped, dict) and bool(scraped)


def _successful_scrape_records(payload: Any) -> list[dict[str, Any]]:
    return [record for record in extract_records(payload) if _scrape_succeeded(record)]


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
    has_input_score_object = isinstance(score, dict)
    score_obj = score if has_input_score_object else {}

    rubric_count_raw = score_obj.get("rubric_count")
    try:
        rubric_count = int(rubric_count_raw) if rubric_count_raw is not None else None
    except (TypeError, ValueError):
        rubric_count = None

    legacy_value = _coerce_float(score_obj.get("value"))
    legacy_max_value = _coerce_float(score_obj.get("max_value"))
    legacy_percent = _coerce_float(score_obj.get("percent"))
    if (
        legacy_percent is None
        and isinstance(legacy_value, (int, float))
        and isinstance(legacy_max_value, (int, float))
        and legacy_max_value > 0
    ):
        legacy_percent = (legacy_value / legacy_max_value) * 100.0

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
            "present": has_input_score_object,
            "rubric_count": rubric_count,
            "lens_scores": _normalize_score_lens_scores(score_obj.get("lens_scores")),
            "legacy_total": {
                "value": legacy_value,
                "max_value": legacy_max_value,
                "percent": legacy_percent,
            },
        },
        "scraped": article.get("scraped"),
        "scrape_error": article.get("scrape_error"),
        "audit": article.get("audit"),
    }

    return normalized


def normalize_articles(payload: Any) -> list[dict[str, Any]]:
    records = _successful_scrape_records(payload)
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


_TAG_COUNT_DISTRIBUTION_LABELS = ("0", "1", "2", "3", "4", "5+")
_SOURCE_EFFECT_PERMUTATIONS = _coerce_int(os.getenv("RSS_SOURCE_EFFECT_PERMUTATIONS"), default=200, minimum=0)
_SOURCE_EFFECT_RANDOM_SEED = 17
_PCA_MAX_COMPONENTS = _coerce_int(os.getenv("RSS_PCA_MAX_COMPONENTS"), default=6, minimum=1)
_MDS_MAX_DIMENSIONS = _coerce_int(os.getenv("RSS_MDS_MAX_DIMENSIONS"), default=3, minimum=1)


def _tag_count_distribution_label(tag_count: int) -> str:
    if tag_count <= 0:
        return "0"
    if tag_count >= 5:
        return "5+"
    return str(tag_count)


def _tag_count_heatmap_label(tag_count: int) -> str:
    if tag_count <= 0:
        return "0"
    if tag_count >= 4:
        return "4+"
    return str(tag_count)


def _lens_max_map_from_analysis(analysis: Any) -> dict[str, float]:
    if not isinstance(analysis, dict):
        return {}
    lens_summary = analysis.get("lens_summary")
    if not isinstance(lens_summary, dict):
        return {}
    lenses = lens_summary.get("lenses", [])
    if not isinstance(lenses, list):
        return {}

    result: dict[str, float] = {}
    for row in lenses:
        if not isinstance(row, dict):
            continue
        name = row.get("name")
        max_total = row.get("max_total")
        if isinstance(name, str) and isinstance(max_total, (int, float)) and max_total > 0:
            result[name] = float(max_total)
    return result


def _record_lens_percentages(record: dict[str, Any], lens_maxima: dict[str, float]) -> dict[str, float]:
    normalized, _mode = _record_lens_percentages_with_mode(record, lens_maxima)
    return normalized


def _record_lens_percentages_with_mode(
    record: dict[str, Any],
    lens_maxima: dict[str, float],
) -> tuple[dict[str, float], str | None]:
    _ = lens_maxima
    score = record.get("score")
    score_obj = score if isinstance(score, dict) else {}
    lens_scores = score_obj.get("lens_scores")
    normalized: dict[str, float] = {}

    if isinstance(lens_scores, dict):
        for lens_name, payload in lens_scores.items():
            if not isinstance(lens_name, str) or not isinstance(payload, dict):
                continue
            percent = _coerce_float(payload.get("percent"))
            if percent is not None:
                normalized[lens_name] = min(max(percent, 0.0), 100.0)
                continue

            value = _coerce_float(payload.get("value"))
            max_value = _coerce_float(payload.get("max_value"))
            if value is not None and max_value is not None and max_value > 0:
                normalized[lens_name] = min(max((value / max_value) * 100.0, 0.0), 100.0)

    if normalized:
        return normalized, "full"
    return {}, None


def _coverage_mode(data_modes: set[str], has_rows: bool) -> str:
    _ = data_modes
    if not has_rows:
        return "no lens data"
    return "all scored articles"


def _ordered_lenses(preferred: list[str], discovered: set[str]) -> list[str]:
    ordered = [name for name in preferred if name in discovered]
    ordered.extend(sorted(discovered - set(ordered)))
    return ordered


def _score_details_for_record(record: dict[str, Any]) -> dict[str, Any]:
    score = record.get("score")
    score_obj = score if isinstance(score, dict) else {}
    present_raw = score_obj.get("present")
    has_score_object = bool(present_raw) if isinstance(present_raw, bool) else isinstance(score, dict)

    lens_scores = score_obj.get("lens_scores")
    lens_scores_obj = lens_scores if isinstance(lens_scores, dict) else {}
    lens_percent_values: list[float] = []
    for lens_payload in lens_scores_obj.values():
        if isinstance(lens_payload, dict):
            percent = _coerce_float(lens_payload.get("percent"))
            if percent is None:
                value = _coerce_float(lens_payload.get("value"))
                max_value = _coerce_float(lens_payload.get("max_value"))
                if value is not None and max_value is not None and max_value > 0:
                    percent = (value / max_value) * 100.0
            if percent is None:
                continue
            lens_percent_values.append(min(max(percent, 0.0), 100.0))
            continue
        if isinstance(lens_payload, (int, float)):
            lens_percent_values.append(min(max(float(lens_payload), 0.0), 100.0))

    has_numeric_lens_signal = bool(lens_percent_values)
    legacy_total = score_obj.get("legacy_total")
    legacy_total_obj = legacy_total if isinstance(legacy_total, dict) else {}
    legacy_value = _coerce_float(legacy_total_obj.get("value"))
    legacy_max_value = _coerce_float(legacy_total_obj.get("max_value"))
    legacy_percent = _coerce_float(legacy_total_obj.get("percent"))
    legacy_fields = [legacy_value, legacy_max_value, legacy_percent]
    has_any_legacy_numeric = any(isinstance(value, (int, float)) for value in legacy_fields)
    has_positive_legacy_signal = any(
        isinstance(value, (int, float)) and float(value) > 0.0 for value in legacy_fields
    )

    if has_numeric_lens_signal:
        is_zero_percent = all(abs(value) < 1e-9 for value in lens_percent_values)
        is_positive_percent = any(value > 0.0 for value in lens_percent_values)
        scored = True
    else:
        is_zero_percent = False
        is_positive_percent = False
        scored = False

    likely_placeholder_zero = (
        has_score_object
        and not scored
        and not has_numeric_lens_signal
        and (not has_any_legacy_numeric or not has_positive_legacy_signal)
    )

    return {
        "status": "scored" if scored else "unscorable",
        "percent": None,
        "has_score_object": has_score_object,
        "is_zero_percent": bool(scored and is_zero_percent),
        "is_positive_percent": bool(scored and is_positive_percent),
        "likely_placeholder_zero": bool(likely_placeholder_zero),
    }


def _is_populated(value: Any) -> bool:
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, list):
        return len(value) > 0
    if isinstance(value, dict):
        return len(value) > 0
    return value is not None


def _data_quality_from_records(records: list[dict[str, Any]]) -> dict[str, Any]:
    total = len(records)
    scored = sum(1 for record in records if _score_details_for_record(record)["status"] == "scored")
    tag_counts = [len(record.get("tags", [])) for record in records if isinstance(record.get("tags"), list)]
    average_tags = (sum(tag_counts) / len(tag_counts)) if tag_counts else 0.0
    missing_ai_summary = sum(1 for record in records if not _is_populated(record.get("ai_summary")))
    missing_published = sum(1 for record in records if not _is_populated(record.get("published_at")))
    missing_source = sum(
        1
        for record in records
        if not _is_populated((record.get("source") or {}).get("name") if isinstance(record.get("source"), dict) else None)
    )

    fields = [
        ("Title", lambda row: row.get("title")),
        ("Link", lambda row: row.get("link")),
        ("Published At", lambda row: row.get("published_at")),
        ("Source Name", lambda row: (row.get("source") or {}).get("name") if isinstance(row.get("source"), dict) else None),
        ("AI Summary", lambda row: row.get("ai_summary")),
        ("Summary", lambda row: row.get("summary")),
        ("Tags", lambda row: row.get("tags")),
        ("Lens Scores", lambda row: (row.get("score") or {}).get("lens_scores") if isinstance(row.get("score"), dict) else None),
    ]

    field_coverage: list[dict[str, Any]] = []
    for label, getter in fields:
        present = sum(1 for record in records if _is_populated(getter(record)))
        missing = max(total - present, 0)
        coverage_percent = (present / total * 100.0) if total else 0.0
        field_coverage.append(
            {
                "field": label,
                "present": present,
                "missing": missing,
                "coverage_percent": coverage_percent,
            }
        )

    return {
        "summary": {
            "total": total,
            "scored": scored,
            "missing_ai_summary": missing_ai_summary,
            "missing_published": missing_published,
            "missing_source": missing_source,
            "average_tags": average_tags,
        },
        "field_coverage": field_coverage,
    }


def _lens_views_from_records(records: list[dict[str, Any]], lens_maxima: dict[str, float]) -> dict[str, Any]:
    article_rows: list[dict[str, Any]] = []
    data_modes: set[str] = set()

    for record in records:
        lens_scores, row_mode = _record_lens_percentages_with_mode(record, lens_maxima)
        if not lens_scores:
            continue

        if row_mode:
            data_modes.add(row_mode)

        source = record.get("source")
        source_obj = source if isinstance(source, dict) else {}
        source_name = _clean_text(source_obj.get("name")) or _clean_text(source_obj.get("id")) or "Unknown"
        strongest_lens, strongest_percent = max(lens_scores.items(), key=lambda item: item[1])
        article_rows.append(
            {
                "id": _clean_text(record.get("id")),
                "title": _clean_text(record.get("title")) or "Untitled",
                "source": source_name,
                "published": _clean_text(record.get("published")) or _clean_text(record.get("published_at")),
                "lens_scores": lens_scores,
                "strongest_lens": strongest_lens,
                "strongest_percent": strongest_percent,
            }
        )

    discovered_lenses = {
        lens_name
        for row in article_rows
        for lens_name, value in row.get("lens_scores", {}).items()
        if isinstance(lens_name, str) and isinstance(value, (int, float))
    }
    lens_names = _ordered_lenses(list(lens_maxima.keys()), discovered_lenses)

    by_source_lens: dict[str, dict[str, list[float]]] = defaultdict(lambda: defaultdict(list))
    by_source_count: Counter[str] = Counter()
    for row in article_rows:
        source_name = str(row.get("source") or "Unknown")
        by_source_count[source_name] += 1

        lens_scores = row.get("lens_scores")
        lens_score_obj = lens_scores if isinstance(lens_scores, dict) else {}
        for lens_name, percent in lens_score_obj.items():
            if isinstance(lens_name, str) and isinstance(percent, (int, float)):
                by_source_lens[source_name][lens_name].append(float(percent))

    source_rows: list[dict[str, Any]] = []
    for source_name, count in sorted(by_source_count.items(), key=lambda item: (-item[1], item[0].lower())):
        lens_means: dict[str, float] = {}
        for lens_name in lens_names:
            values = by_source_lens[source_name].get(lens_name, [])
            if values:
                lens_means[lens_name] = sum(values) / len(values)
        source_rows.append(
            {
                "source": source_name,
                "article_count": count,
                "lens_means": lens_means,
            }
        )

    source_lens_average_rows: list[dict[str, Any]] = []
    for lens_name in lens_names:
        values = [
            float(row["lens_means"][lens_name])
            for row in source_rows
            if isinstance(row.get("lens_means"), dict) and isinstance(row["lens_means"].get(lens_name), (int, float))
        ]
        source_lens_average_rows.append(
            {
                "lens": lens_name,
                "count": len(values),
                "mean": (sum(values) / len(values)) if values else None,
            }
        )

    lens_values: dict[str, list[float]] = defaultdict(list)
    lens_source_values: dict[str, dict[str, list[float]]] = defaultdict(lambda: defaultdict(list))
    for row in article_rows:
        source_name = str(row.get("source") or "Unknown")
        lens_scores = row.get("lens_scores")
        lens_score_obj = lens_scores if isinstance(lens_scores, dict) else {}
        for lens_name, value in lens_score_obj.items():
            if isinstance(lens_name, str) and isinstance(value, (int, float)):
                percent = float(value)
                lens_values[lens_name].append(percent)
                lens_source_values[lens_name][source_name].append(percent)

    stability_rows: list[dict[str, Any]] = []
    for lens_name in lens_names:
        values = lens_values.get(lens_name, [])
        if not values:
            continue
        mean_value = statistics.fmean(values)
        stddev = statistics.pstdev(values) if len(values) > 1 else 0.0
        min_value = min(values)
        max_value = max(values)
        source_means = [
            statistics.fmean(source_values)
            for source_values in lens_source_values[lens_name].values()
            if source_values
        ]
        source_gap = (max(source_means) - min(source_means)) if len(source_means) >= 2 else 0.0
        stability_rows.append(
            {
                "lens": lens_name,
                "count": len(values),
                "mean": mean_value,
                "stddev": stddev,
                "cv_percent": (stddev / mean_value) * 100.0 if mean_value > 0 else None,
                "min": min_value,
                "max": max_value,
                "range": max_value - min_value,
                "source_count": len(source_means),
                "source_gap": source_gap,
            }
        )

    stability_rows.sort(
        key=lambda row: (float(row.get("stddev") or 0.0), float(row.get("range") or 0.0)),
        reverse=True,
    )

    dominant_counter: Counter[str] = Counter()
    for row in article_rows:
        strongest_lens = row.get("strongest_lens")
        if isinstance(strongest_lens, str) and strongest_lens:
            dominant_counter[strongest_lens] += 1

    lens_average_rows: list[dict[str, Any]] = []
    for lens_name in lens_names:
        values = lens_values.get(lens_name, [])
        lens_average_rows.append(
            {
                "lens": lens_name,
                "count": len(values),
                "mean": (sum(values) / len(values)) if values else None,
            }
        )

    dominant_lens_counts = [
        {"lens": lens_name, "count": count}
        for lens_name, count in dominant_counter.most_common()
    ]

    stability_avg_stddev = (
        statistics.fmean([float(row.get("stddev") or 0.0) for row in stability_rows])
        if stability_rows
        else None
    )

    coverage_mode = _coverage_mode(data_modes, has_rows=bool(article_rows))
    return {
        "coverage_mode": coverage_mode,
        "lens_names": lens_names,
        "article_rows": article_rows,
        "source_rows": source_rows,
        "stability_rows": stability_rows,
        "summary": {
            "article_count": len(article_rows),
            "dominant_lens_counts": dominant_lens_counts,
            "lens_average_rows": lens_average_rows,
            "source_count": len(source_rows),
            "covered_articles": sum(int(row.get("article_count") or 0) for row in source_rows),
            "source_lens_average_rows": source_lens_average_rows,
            "stability_lens_count": len(stability_rows),
            "stability_avg_stddev": stability_avg_stddev,
            "stability_top_lens": stability_rows[0].get("lens") if stability_rows else None,
            "stability_total_samples": sum(int(row.get("count") or 0) for row in stability_rows),
        },
    }


def _source_tag_views_from_aggregates(
    source_tag_counter: Counter[tuple[str, str]],
    source_tag_matrix: list[dict[str, Any]],
    source_tag_totals: list[dict[str, Any]],
    tag_totals: list[dict[str, Any]],
) -> dict[str, Any]:
    source_labels = [
        str(row.get("source")).strip()
        for row in source_tag_totals
        if isinstance(row, dict) and str(row.get("source")).strip() and isinstance(row.get("count"), (int, float))
    ]
    tag_labels = [
        str(row.get("tag")).strip()
        for row in tag_totals
        if isinstance(row, dict) and str(row.get("tag")).strip() and isinstance(row.get("count"), (int, float))
    ]

    source_totals_by_name = {
        str(row.get("source")).strip(): int(row.get("count", 0) or 0)
        for row in source_tag_totals
        if isinstance(row, dict) and str(row.get("source")).strip()
    }
    tag_rows_by_source: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for (source_name, tag_name), count in source_tag_counter.items():
        if not source_name or not tag_name:
            continue
        tag_rows_by_source[str(source_name)].append({"tag": str(tag_name), "count": int(count)})

    source_rows: list[dict[str, Any]] = []
    for source_name in source_labels:
        tag_rows = tag_rows_by_source.get(source_name, [])
        tag_rows.sort(key=lambda row: (-int(row.get("count", 0) or 0), str(row.get("tag", "")).lower()))
        source_rows.append(
            {
                "source": source_name,
                "count": source_totals_by_name.get(source_name, 0),
                "tags": tag_rows,
            }
        )

    total_assignments = sum(
        int(row.get("count", 0) or 0)
        for row in source_tag_matrix
        if isinstance(row, dict)
    )
    non_zero_cells = sum(
        1
        for row in source_tag_matrix
        if isinstance(row, dict) and int(row.get("count", 0) or 0) > 0
    )

    return {
        "source_labels": source_labels,
        "tag_labels": tag_labels,
        "source_rows": source_rows,
        "summary": {
            "source_count": len(source_labels),
            "tag_count": len(tag_labels),
            "matrix_rows": len(source_tag_matrix),
            "non_zero_cells": non_zero_cells,
            "total_assignments": total_assignments,
        },
    }


def _lens_inventory_from_records(
    records: list[dict[str, Any]],
    analysis: dict[str, Any] | None,
    lens_maxima: dict[str, float],
) -> dict[str, Any]:
    lens_summary = analysis.get("lens_summary") if isinstance(analysis, dict) else None
    lens_summary_obj = lens_summary if isinstance(lens_summary, dict) else {}
    upstream_lenses = lens_summary_obj.get("lenses")

    items_total = len(records)
    items_total_raw = lens_summary_obj.get("items_total")
    if isinstance(items_total_raw, (int, float)) and items_total_raw >= 0:
        items_total = int(items_total_raw)

    coverage_counter: Counter[str] = Counter()
    data_modes: set[str] = set()
    for record in records:
        lens_scores, row_mode = _record_lens_percentages_with_mode(record, lens_maxima)
        if not lens_scores:
            continue
        for lens_name in lens_scores.keys():
            coverage_counter[lens_name] += 1
        if row_mode:
            data_modes.add(row_mode)

    preferred_names: list[str] = []
    row_by_lens: dict[str, dict[str, Any]] = {}
    if isinstance(upstream_lenses, list):
        for row in upstream_lenses:
            if not isinstance(row, dict):
                continue
            lens_name = _clean_text(row.get("name"))
            if not lens_name:
                continue
            preferred_names.append(lens_name)

            rubric_count = row.get("rubric_count")
            rubric_value = int(rubric_count) if isinstance(rubric_count, (int, float)) else None

            max_total = _coerce_float(row.get("max_total"))
            if max_total is not None and max_total <= 0:
                max_total = None
            if max_total is None:
                fallback_max = lens_maxima.get(lens_name)
                if isinstance(fallback_max, (int, float)) and fallback_max > 0:
                    max_total = float(fallback_max)

            items_with_scores = row.get("items_with_scores")
            items_with_scores_value = int(items_with_scores) if isinstance(items_with_scores, (int, float)) else None
            if isinstance(items_with_scores_value, int) and items_with_scores_value < 0:
                items_with_scores_value = None

            row_by_lens[lens_name] = {
                "name": lens_name,
                "rubric_count": rubric_value,
                "max_total": max_total,
                "items_with_scores": items_with_scores_value,
            }

    for lens_name, count in coverage_counter.items():
        row = row_by_lens.setdefault(
            lens_name,
            {
                "name": lens_name,
                "rubric_count": None,
                "max_total": None,
                "items_with_scores": None,
            },
        )
        existing_count = row.get("items_with_scores")
        if not isinstance(existing_count, int) or count > existing_count:
            row["items_with_scores"] = count

    for lens_name, max_total in lens_maxima.items():
        if not isinstance(max_total, (int, float)) or max_total <= 0:
            continue
        row = row_by_lens.setdefault(
            lens_name,
            {
                "name": lens_name,
                "rubric_count": None,
                "max_total": None,
                "items_with_scores": None,
            },
        )
        if not isinstance(row.get("max_total"), (int, float)):
            row["max_total"] = float(max_total)

    preferred = list(dict.fromkeys(preferred_names + list(lens_maxima.keys())))
    ordered_names = _ordered_lenses(preferred, set(row_by_lens.keys()))
    rows = [row_by_lens[name] for name in ordered_names]

    aggregation = _clean_text(lens_summary_obj.get("aggregation"))
    if not aggregation:
        aggregation = "upstream_summary" if isinstance(upstream_lenses, list) and upstream_lenses else "backend_derived"

    return {
        "coverage_mode": _coverage_mode(data_modes, has_rows=bool(coverage_counter)),
        "items_total": items_total,
        "aggregation": aggregation,
        "lenses": rows,
    }


def _pairwise_stats(xs: list[float], ys: list[float]) -> tuple[float | None, float | None]:
    if not xs or not ys or len(xs) != len(ys):
        return None, None
    count = len(xs)
    if count == 0:
        return None, None

    mean_x = sum(xs) / count
    mean_y = sum(ys) / count
    covariance = sum((x - mean_x) * (y - mean_y) for x, y in zip(xs, ys)) / count

    var_x = sum((x - mean_x) ** 2 for x in xs) / count
    var_y = sum((y - mean_y) ** 2 for y in ys) / count
    if var_x <= 0 or var_y <= 0:
        return covariance, None
    correlation = covariance / math.sqrt(var_x * var_y)
    return covariance, correlation


def _sorted_pair_rankings(
    lens_names: list[str],
    matrix: list[list[float | int | None]],
    matrix_key: str,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for row_index, lens_a in enumerate(lens_names):
        for col_index in range(row_index + 1, len(lens_names)):
            if row_index >= len(matrix) or not isinstance(matrix[row_index], list):
                continue
            row = matrix[row_index]
            if col_index >= len(row):
                continue
            value = row[col_index]
            if not isinstance(value, (int, float)):
                continue
            rows.append(
                {
                    "lens_a": lens_a,
                    "lens_b": lens_names[col_index],
                    "value": float(value),
                }
            )

    if matrix_key == "pairwise":
        rows.sort(key=lambda row: float(row.get("value") or 0.0), reverse=True)
    else:
        rows.sort(
            key=lambda row: (abs(float(row.get("value") or 0.0)), float(row.get("value") or 0.0)),
            reverse=True,
        )
    return rows


def _pair_ranking_summary(lens_names: list[str], rows: list[dict[str, Any]]) -> dict[str, Any]:
    strongest_row = rows[0] if rows else {}
    strongest_value = strongest_row.get("value")
    strongest_pair = None
    if isinstance(strongest_row.get("lens_a"), str) and isinstance(strongest_row.get("lens_b"), str):
        strongest_pair = f"{strongest_row['lens_a']} / {strongest_row['lens_b']}"

    return {
        "lens_count": len(lens_names),
        "pair_count": len(rows),
        "strongest_pair": strongest_pair,
        "strongest_value": float(strongest_value) if isinstance(strongest_value, (int, float)) else None,
    }


def _lens_correlations_from_records(
    article_lens_percentages: list[dict[str, float]],
    preferred_lenses: list[str] | None = None,
) -> dict[str, Any]:
    discovered = {
        lens_name
        for row in article_lens_percentages
        for lens_name, value in row.items()
        if isinstance(lens_name, str) and isinstance(value, (int, float))
    }
    if preferred_lenses:
        ordered = [name for name in preferred_lenses if name in discovered]
        ordered.extend(sorted(discovered - set(ordered)))
        lens_names = ordered
    else:
        lens_names = sorted(discovered)

    size = len(lens_names)
    if size == 0:
        return {
            "lenses": [],
            "correlation": {"raw": [], "normalized": []},
            "covariance": {"raw": [], "normalized": []},
            "pairwise_counts": [],
            "pair_rankings": {
                "corr_raw": [],
                "corr_norm": [],
                "cov_raw": [],
                "cov_norm": [],
                "pairwise": [],
            },
            "summary_by_matrix": {},
        }

    corr_raw: list[list[float | None]] = [[None for _ in range(size)] for _ in range(size)]
    corr_norm: list[list[float | None]] = [[None for _ in range(size)] for _ in range(size)]
    cov_raw: list[list[float | None]] = [[None for _ in range(size)] for _ in range(size)]
    cov_norm: list[list[float | None]] = [[None for _ in range(size)] for _ in range(size)]
    pairwise_counts: list[list[int | None]] = [[None for _ in range(size)] for _ in range(size)]

    for row_index, lens_a in enumerate(lens_names):
        for col_index, lens_b in enumerate(lens_names):
            xs: list[float] = []
            ys: list[float] = []
            for row in article_lens_percentages:
                a = row.get(lens_a)
                b = row.get(lens_b)
                if isinstance(a, (int, float)) and isinstance(b, (int, float)):
                    xs.append(float(a))
                    ys.append(float(b))
            count = len(xs)
            pairwise_counts[row_index][col_index] = count
            if count == 0:
                continue

            covariance, correlation = _pairwise_stats(xs, ys)
            if row_index == col_index:
                if covariance is None:
                    covariance = 0.0
                if correlation is None:
                    correlation = 1.0

            cov_raw[row_index][col_index] = covariance
            cov_norm[row_index][col_index] = (
                (covariance / 10000.0) if isinstance(covariance, (int, float)) else None
            )
            corr_raw[row_index][col_index] = correlation
            corr_norm[row_index][col_index] = correlation

    pair_rankings = {
        "corr_raw": _sorted_pair_rankings(lens_names, corr_raw, "corr_raw"),
        "corr_norm": _sorted_pair_rankings(lens_names, corr_norm, "corr_norm"),
        "cov_raw": _sorted_pair_rankings(lens_names, cov_raw, "cov_raw"),
        "cov_norm": _sorted_pair_rankings(lens_names, cov_norm, "cov_norm"),
        "pairwise": _sorted_pair_rankings(lens_names, pairwise_counts, "pairwise"),
    }
    summary_by_matrix = {
        matrix_key: _pair_ranking_summary(lens_names, rows)
        for matrix_key, rows in pair_rankings.items()
    }

    return {
        "lenses": lens_names,
        "correlation": {"raw": corr_raw, "normalized": corr_norm},
        "covariance": {"raw": cov_raw, "normalized": cov_norm},
        "pairwise_counts": pairwise_counts,
        "pair_rankings": pair_rankings,
        "summary_by_matrix": summary_by_matrix,
    }


def _lens_pca_from_records(
    article_lens_percentages: list[dict[str, float]],
    source_labels: list[str],
    article_meta_rows: list[dict[str, Any]] | None = None,
    preferred_lenses: list[str] | None = None,
    max_components: int = _PCA_MAX_COMPONENTS,
) -> dict[str, Any]:
    if np is None:
        return {
            "status": "unavailable",
            "reason": "numpy is unavailable; PCA cannot be computed.",
            "n_articles": 0,
            "n_lenses": 0,
            "source_counts": {},
            "lenses": [],
            "components": [],
            "explained_variance": [],
            "loadings": {"lenses": [], "components": [], "matrix": []},
            "component_summary": [],
            "variance_drivers": [],
            "article_points": [],
            "source_centroids": [],
            "basis": "zscore_lens_percentages",
            "coverage_mode": "none",
        }

    if not article_lens_percentages or len(article_lens_percentages) != len(source_labels):
        return {
            "status": "unavailable",
            "reason": "No article-level lens rows available for PCA.",
            "n_articles": 0,
            "n_lenses": 0,
            "source_counts": {},
            "lenses": [],
            "components": [],
            "explained_variance": [],
            "loadings": {"lenses": [], "components": [], "matrix": []},
            "component_summary": [],
            "variance_drivers": [],
            "article_points": [],
            "source_centroids": [],
            "basis": "zscore_lens_percentages",
            "coverage_mode": "none",
        }

    discovered = {
        lens_name
        for row in article_lens_percentages
        for lens_name, value in row.items()
        if isinstance(lens_name, str) and isinstance(value, (int, float)) and math.isfinite(float(value))
    }
    if preferred_lenses:
        ordered = [lens_name for lens_name in preferred_lenses if lens_name in discovered]
        ordered.extend(sorted(discovered - set(ordered)))
        lens_names = ordered
    else:
        lens_names = sorted(discovered)

    def _complete_matrix(required_lenses: list[str]) -> tuple[list[list[float]], list[str], list[int]]:
        matrix: list[list[float]] = []
        labels: list[str] = []
        kept_indexes: list[int] = []
        for row_index, (row, label) in enumerate(zip(article_lens_percentages, source_labels)):
            values: list[float] = []
            for lens_name in required_lenses:
                value = row.get(lens_name)
                if not isinstance(value, (int, float)) or not math.isfinite(float(value)):
                    values = []
                    break
                values.append(float(value))
            if values:
                matrix.append(values)
                labels.append(str(label))
                kept_indexes.append(row_index)
        return matrix, labels, kept_indexes

    matrix, matrix_labels, kept_indexes = _complete_matrix(lens_names)
    if not matrix and article_lens_percentages:
        shared = set(article_lens_percentages[0].keys())
        for row in article_lens_percentages[1:]:
            shared &= set(row.keys())
        shared = {
            lens_name
            for lens_name in shared
            if isinstance(lens_name, str)
            and all(isinstance(row.get(lens_name), (int, float)) and math.isfinite(float(row[lens_name])) for row in article_lens_percentages)
        }
        if preferred_lenses:
            reduced_lenses = [lens_name for lens_name in preferred_lenses if lens_name in shared]
            reduced_lenses.extend(sorted(shared - set(reduced_lenses)))
        else:
            reduced_lenses = sorted(shared)
        if reduced_lenses:
            lens_names = reduced_lenses
            matrix, matrix_labels, kept_indexes = _complete_matrix(lens_names)

    source_counts: Counter[str] = Counter(matrix_labels)
    if not matrix:
        return {
            "status": "unavailable",
            "reason": "Need complete source-lens rows to run PCA.",
            "n_articles": 0,
            "n_lenses": len(lens_names),
            "source_counts": dict(source_counts),
            "lenses": lens_names,
            "components": [],
            "explained_variance": [],
            "loadings": {"lenses": lens_names, "components": [], "matrix": []},
            "component_summary": [],
            "variance_drivers": [],
            "article_points": [],
            "source_centroids": [],
            "basis": "zscore_lens_percentages",
            "coverage_mode": "none",
        }

    n_articles = len(matrix)
    n_lenses = len(lens_names)
    if n_articles < 2 or n_lenses < 1:
        return {
            "status": "unavailable",
            "reason": "Need at least 2 complete rows and 1 lens to run PCA.",
            "n_articles": n_articles,
            "n_lenses": n_lenses,
            "source_counts": dict(source_counts),
            "lenses": lens_names,
            "components": [],
            "explained_variance": [],
            "loadings": {"lenses": lens_names, "components": [], "matrix": []},
            "component_summary": [],
            "variance_drivers": [],
            "article_points": [],
            "source_centroids": [],
            "basis": "zscore_lens_percentages",
            "coverage_mode": "none",
        }

    matrix_np = np.asarray(matrix, dtype=float)
    means_np = matrix_np.mean(axis=0)
    centered_np = matrix_np - means_np
    stds_np = centered_np.std(axis=0, ddof=0)
    safe_stds_np = np.where(stds_np > 1e-12, stds_np, 1.0)
    standardized_np = centered_np / safe_stds_np

    covariance_np = (standardized_np.T @ standardized_np) / max(n_articles - 1, 1)
    eigenvalues_np, eigenvectors_np = np.linalg.eigh(covariance_np)
    sort_order = np.argsort(eigenvalues_np)[::-1]
    eigenvalues_np = np.maximum(eigenvalues_np[sort_order], 0.0)
    eigenvectors_np = eigenvectors_np[:, sort_order]

    non_zero_components = int(sum(float(value) > 1e-12 for value in eigenvalues_np.tolist()))
    if non_zero_components == 0:
        return {
            "status": "unavailable",
            "reason": "PCA eigenvalues are all zero for the complete-row matrix.",
            "n_articles": n_articles,
            "n_lenses": n_lenses,
            "source_counts": dict(source_counts),
            "lenses": lens_names,
            "components": [],
            "explained_variance": [],
            "loadings": {"lenses": lens_names, "components": [], "matrix": []},
            "component_summary": [],
            "variance_drivers": [],
            "article_points": [],
            "source_centroids": [],
            "basis": "zscore_lens_percentages",
            "coverage_mode": "complete_rows",
        }

    component_count = min(max_components, n_lenses, max(non_zero_components, 1))
    loadings_np = eigenvectors_np[:, :component_count].T
    scores_np = standardized_np @ eigenvectors_np[:, :component_count]

    for component_index in range(component_count):
        component_values = loadings_np[component_index]
        dominant_index = int(np.argmax(np.abs(component_values)))
        if component_values[dominant_index] < 0:
            loadings_np[component_index] = -component_values
            scores_np[:, component_index] = -scores_np[:, component_index]

    total_variance = float(np.sum(eigenvalues_np))
    explained_ratio = [
        (float(value) / total_variance) if total_variance > 0 else 0.0
        for value in eigenvalues_np[:component_count].tolist()
    ]

    explained_rows: list[dict[str, Any]] = []
    running_ratio = 0.0
    component_labels: list[str] = []
    for component_index in range(component_count):
        label = f"PC{component_index + 1}"
        component_labels.append(label)
        ratio = explained_ratio[component_index]
        running_ratio += ratio
        explained_rows.append(
            {
                "component": label,
                "eigenvalue": float(eigenvalues_np[component_index]),
                "explained_variance_ratio": ratio,
                "cumulative_variance_ratio": running_ratio,
            }
        )

    component_summary: list[dict[str, Any]] = []
    for component_index, component_label in enumerate(component_labels):
        pairs = [
            (lens_name, float(loadings_np[component_index][lens_index]))
            for lens_index, lens_name in enumerate(lens_names)
        ]
        sorted_abs = sorted(pairs, key=lambda item: abs(item[1]), reverse=True)
        top_positive = [
            {"lens": lens_name, "loading": loading}
            for lens_name, loading in sorted((pair for pair in pairs if pair[1] > 0), key=lambda item: item[1], reverse=True)[:3]
        ]
        top_negative = [
            {"lens": lens_name, "loading": loading}
            for lens_name, loading in sorted((pair for pair in pairs if pair[1] < 0), key=lambda item: item[1])[:3]
        ]
        component_summary.append(
            {
                "component": component_label,
                "explained_variance_ratio": explained_ratio[component_index],
                "strongest_loadings": [
                    {"lens": lens_name, "loading": loading, "abs_loading": abs(loading)}
                    for lens_name, loading in sorted_abs[:5]
                ],
                "top_positive": top_positive,
                "top_negative": top_negative,
            }
        )

    variance_drivers: list[dict[str, Any]] = []
    for lens_index, lens_name in enumerate(lens_names):
        weighted_contribution = 0.0
        for component_index in range(component_count):
            weighted_contribution += (float(loadings_np[component_index][lens_index]) ** 2) * explained_ratio[component_index]
        variance_drivers.append(
            {
                "lens": lens_name,
                "weighted_contribution": weighted_contribution,
                "pc1_loading": float(loadings_np[0][lens_index]) if component_count >= 1 else None,
                "pc2_loading": float(loadings_np[1][lens_index]) if component_count >= 2 else None,
            }
        )
    variance_drivers.sort(key=lambda row: float(row.get("weighted_contribution") or 0.0), reverse=True)

    article_meta = article_meta_rows if isinstance(article_meta_rows, list) else []
    article_points: list[dict[str, Any]] = []
    for row_offset, row_index in enumerate(kept_indexes):
        meta_row = article_meta[row_index] if row_index < len(article_meta) and isinstance(article_meta[row_index], dict) else {}
        title = _clean_text(meta_row.get("title")) or "Untitled"
        if len(title) > 160:
            title = f"{title[:157]}..."
        point_source = _clean_text(meta_row.get("source")) or _clean_text(matrix_labels[row_offset]) or "Unknown"
        article_points.append(
            {
                "id": _clean_text(meta_row.get("id")),
                "title": title,
                "source": point_source,
                "published_at": _clean_text(meta_row.get("published_at")),
                "strongest_lens": _clean_text(meta_row.get("strongest_lens")),
                "strongest_percent": _coerce_float(meta_row.get("strongest_percent")),
                "pc1": float(scores_np[row_offset][0]) if component_count >= 1 else None,
                "pc2": float(scores_np[row_offset][1]) if component_count >= 2 else None,
                "pc3": float(scores_np[row_offset][2]) if component_count >= 3 else None,
            }
        )

    by_source_points: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in article_points:
        source_name = _clean_text(row.get("source")) or "Unknown"
        by_source_points[source_name].append(row)

    source_centroids: list[dict[str, Any]] = []
    for source_name, rows in by_source_points.items():
        pc1_values = [float(row["pc1"]) for row in rows if isinstance(row.get("pc1"), (int, float))]
        pc2_values = [float(row["pc2"]) for row in rows if isinstance(row.get("pc2"), (int, float))]
        pc3_values = [float(row["pc3"]) for row in rows if isinstance(row.get("pc3"), (int, float))]
        source_centroids.append(
            {
                "source": source_name,
                "count": len(rows),
                "pc1": (sum(pc1_values) / len(pc1_values)) if pc1_values else None,
                "pc2": (sum(pc2_values) / len(pc2_values)) if pc2_values else None,
                "pc3": (sum(pc3_values) / len(pc3_values)) if pc3_values else None,
            }
        )
    source_centroids.sort(key=lambda row: (-int(row.get("count") or 0), str(row.get("source", "")).lower()))

    return {
        "status": "ok",
        "reason": "",
        "n_articles": n_articles,
        "n_lenses": n_lenses,
        "source_counts": dict(source_counts),
        "lenses": lens_names,
        "components": component_labels,
        "explained_variance": explained_rows,
        "loadings": {
            "lenses": lens_names,
            "components": component_labels,
            "matrix": loadings_np.tolist(),
        },
        "component_summary": component_summary,
        "variance_drivers": variance_drivers,
        "article_points": article_points,
        "source_centroids": source_centroids,
        "basis": "zscore_lens_percentages",
        "coverage_mode": "complete_rows",
    }


def _lens_mds_from_records(
    article_lens_percentages: list[dict[str, float]],
    source_labels: list[str],
    article_meta_rows: list[dict[str, Any]] | None = None,
    preferred_lenses: list[str] | None = None,
    max_dimensions: int = _MDS_MAX_DIMENSIONS,
) -> dict[str, Any]:
    empty_payload = {
        "status": "unavailable",
        "reason": "",
        "n_articles": 0,
        "n_lenses": 0,
        "source_counts": {},
        "lenses": [],
        "dimensions": [],
        "dimension_strength": [],
        "stress": None,
        "article_points": [],
        "source_centroids": [],
        "basis": "euclidean_distance_on_zscore_lens_percentages",
        "coverage_mode": "none",
    }
    if np is None:
        payload = dict(empty_payload)
        payload["reason"] = "numpy is unavailable; MDS cannot be computed."
        return payload

    if not article_lens_percentages or len(article_lens_percentages) != len(source_labels):
        payload = dict(empty_payload)
        payload["reason"] = "No article-level lens rows available for MDS."
        return payload

    discovered = {
        lens_name
        for row in article_lens_percentages
        for lens_name, value in row.items()
        if isinstance(lens_name, str) and isinstance(value, (int, float)) and math.isfinite(float(value))
    }
    if preferred_lenses:
        ordered = [lens_name for lens_name in preferred_lenses if lens_name in discovered]
        ordered.extend(sorted(discovered - set(ordered)))
        lens_names = ordered
    else:
        lens_names = sorted(discovered)

    def _complete_matrix(required_lenses: list[str]) -> tuple[list[list[float]], list[str], list[int]]:
        matrix: list[list[float]] = []
        labels: list[str] = []
        kept_indexes: list[int] = []
        for row_index, (row, label) in enumerate(zip(article_lens_percentages, source_labels)):
            values: list[float] = []
            for lens_name in required_lenses:
                value = row.get(lens_name)
                if not isinstance(value, (int, float)) or not math.isfinite(float(value)):
                    values = []
                    break
                values.append(float(value))
            if values:
                matrix.append(values)
                labels.append(str(label))
                kept_indexes.append(row_index)
        return matrix, labels, kept_indexes

    matrix, matrix_labels, kept_indexes = _complete_matrix(lens_names)
    if not matrix and article_lens_percentages:
        shared = set(article_lens_percentages[0].keys())
        for row in article_lens_percentages[1:]:
            shared &= set(row.keys())
        shared = {
            lens_name
            for lens_name in shared
            if isinstance(lens_name, str)
            and all(isinstance(row.get(lens_name), (int, float)) and math.isfinite(float(row[lens_name])) for row in article_lens_percentages)
        }
        if preferred_lenses:
            reduced_lenses = [lens_name for lens_name in preferred_lenses if lens_name in shared]
            reduced_lenses.extend(sorted(shared - set(reduced_lenses)))
        else:
            reduced_lenses = sorted(shared)
        if reduced_lenses:
            lens_names = reduced_lenses
            matrix, matrix_labels, kept_indexes = _complete_matrix(lens_names)

    source_counts: Counter[str] = Counter(matrix_labels)
    if not matrix:
        payload = dict(empty_payload)
        payload["reason"] = "Need complete source-lens rows to run MDS."
        payload["n_lenses"] = len(lens_names)
        payload["source_counts"] = dict(source_counts)
        payload["lenses"] = lens_names
        return payload

    n_articles = len(matrix)
    n_lenses = len(lens_names)
    if n_articles < 2 or n_lenses < 1:
        payload = dict(empty_payload)
        payload["reason"] = "Need at least 2 complete rows and 1 lens to run MDS."
        payload["n_articles"] = n_articles
        payload["n_lenses"] = n_lenses
        payload["source_counts"] = dict(source_counts)
        payload["lenses"] = lens_names
        return payload

    matrix_np = np.asarray(matrix, dtype=float)
    means_np = matrix_np.mean(axis=0)
    centered_np = matrix_np - means_np
    stds_np = centered_np.std(axis=0, ddof=0)
    safe_stds_np = np.where(stds_np > 1e-12, stds_np, 1.0)
    standardized_np = centered_np / safe_stds_np

    diff_np = standardized_np[:, np.newaxis, :] - standardized_np[np.newaxis, :, :]
    distance_sq_np = np.maximum(np.sum(diff_np * diff_np, axis=2), 0.0)
    n = n_articles
    centering_np = np.eye(n) - np.ones((n, n)) / float(n)
    gram_np = -0.5 * centering_np @ distance_sq_np @ centering_np

    eigenvalues_np, eigenvectors_np = np.linalg.eigh(gram_np)
    sort_order = np.argsort(eigenvalues_np)[::-1]
    eigenvalues_np = eigenvalues_np[sort_order]
    eigenvectors_np = eigenvectors_np[:, sort_order]

    positive_mask = eigenvalues_np > 1e-12
    positive_values_np = eigenvalues_np[positive_mask]
    positive_vectors_np = eigenvectors_np[:, positive_mask]
    if len(positive_values_np) == 0:
        payload = dict(empty_payload)
        payload["reason"] = "MDS eigenvalues are all non-positive for the complete-row matrix."
        payload["n_articles"] = n_articles
        payload["n_lenses"] = n_lenses
        payload["source_counts"] = dict(source_counts)
        payload["lenses"] = lens_names
        payload["coverage_mode"] = "complete_rows"
        return payload

    dimension_count = min(max_dimensions, len(positive_values_np))
    selected_values_np = positive_values_np[:dimension_count]
    selected_vectors_np = positive_vectors_np[:, :dimension_count]
    coords_np = selected_vectors_np * np.sqrt(selected_values_np)

    for dim_index in range(dimension_count):
        dim_values = coords_np[:, dim_index]
        dominant_index = int(np.argmax(np.abs(dim_values)))
        if dim_values[dominant_index] < 0:
            coords_np[:, dim_index] = -dim_values

    total_strength = float(np.sum(positive_values_np))
    dimension_labels: list[str] = []
    dimension_strength: list[dict[str, Any]] = []
    running_ratio = 0.0
    for dim_index in range(dimension_count):
        label = f"MDS{dim_index + 1}"
        dimension_labels.append(label)
        eigenvalue = float(selected_values_np[dim_index])
        ratio = (eigenvalue / total_strength) if total_strength > 0 else 0.0
        running_ratio += ratio
        dimension_strength.append(
            {
                "dimension": label,
                "eigenvalue": eigenvalue,
                "strength_ratio": ratio,
                "cumulative_strength_ratio": running_ratio,
            }
        )

    original_dist_np = np.sqrt(distance_sq_np)
    approx_diff_np = coords_np[:, np.newaxis, :] - coords_np[np.newaxis, :, :]
    approx_dist_np = np.sqrt(np.maximum(np.sum(approx_diff_np * approx_diff_np, axis=2), 0.0))
    tri_upper = np.triu_indices(n, k=1)
    numerator = float(np.sum(np.square(original_dist_np[tri_upper] - approx_dist_np[tri_upper])))
    denominator = float(np.sum(np.square(original_dist_np[tri_upper])))
    stress = math.sqrt(numerator / denominator) if denominator > 1e-12 else 0.0

    article_meta = article_meta_rows if isinstance(article_meta_rows, list) else []
    article_points: list[dict[str, Any]] = []
    for row_offset, row_index in enumerate(kept_indexes):
        meta_row = article_meta[row_index] if row_index < len(article_meta) and isinstance(article_meta[row_index], dict) else {}
        title = _clean_text(meta_row.get("title")) or "Untitled"
        if len(title) > 160:
            title = f"{title[:157]}..."
        point_source = _clean_text(meta_row.get("source")) or _clean_text(matrix_labels[row_offset]) or "Unknown"
        article_points.append(
            {
                "id": _clean_text(meta_row.get("id")),
                "title": title,
                "source": point_source,
                "published_at": _clean_text(meta_row.get("published_at")),
                "strongest_lens": _clean_text(meta_row.get("strongest_lens")),
                "strongest_percent": _coerce_float(meta_row.get("strongest_percent")),
                "mds1": float(coords_np[row_offset][0]) if dimension_count >= 1 else None,
                "mds2": float(coords_np[row_offset][1]) if dimension_count >= 2 else None,
                "mds3": float(coords_np[row_offset][2]) if dimension_count >= 3 else None,
            }
        )

    by_source_points: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in article_points:
        source_name = _clean_text(row.get("source")) or "Unknown"
        by_source_points[source_name].append(row)

    source_centroids: list[dict[str, Any]] = []
    for source_name, rows in by_source_points.items():
        mds1_values = [float(row["mds1"]) for row in rows if isinstance(row.get("mds1"), (int, float))]
        mds2_values = [float(row["mds2"]) for row in rows if isinstance(row.get("mds2"), (int, float))]
        mds3_values = [float(row["mds3"]) for row in rows if isinstance(row.get("mds3"), (int, float))]
        source_centroids.append(
            {
                "source": source_name,
                "count": len(rows),
                "mds1": (sum(mds1_values) / len(mds1_values)) if mds1_values else None,
                "mds2": (sum(mds2_values) / len(mds2_values)) if mds2_values else None,
                "mds3": (sum(mds3_values) / len(mds3_values)) if mds3_values else None,
            }
        )
    source_centroids.sort(key=lambda row: (-int(row.get("count") or 0), str(row.get("source", "")).lower()))

    return {
        "status": "ok",
        "reason": "",
        "n_articles": n_articles,
        "n_lenses": n_lenses,
        "source_counts": dict(source_counts),
        "lenses": lens_names,
        "dimensions": dimension_labels,
        "dimension_strength": dimension_strength,
        "stress": stress,
        "article_points": article_points,
        "source_centroids": source_centroids,
        "basis": "euclidean_distance_on_zscore_lens_percentages",
        "coverage_mode": "complete_rows",
    }


def _lens_separation_from_records(
    article_lens_percentages: list[dict[str, float]],
    source_labels: list[str],
    preferred_lenses: list[str] | None = None,
) -> dict[str, Any]:
    empty_payload = {
        "status": "unavailable",
        "reason": "",
        "n_articles": 0,
        "n_lenses": 0,
        "n_sources": 0,
        "source_counts": {},
        "lenses": [],
        "basis": "euclidean_distance_on_zscore_lens_percentages",
        "coverage_mode": "none",
        "within_source_mean_distance": None,
        "between_source_centroid_mean_distance": None,
        "between_source_centroid_min_distance": None,
        "separation_ratio": None,
        "silhouette_like_mean": None,
        "silhouette_like_by_source": [],
        "source_centroids": [],
        "centroid_distances": [],
    }
    if np is None:
        payload = dict(empty_payload)
        payload["reason"] = "numpy is unavailable; lens separation diagnostics cannot be computed."
        return payload

    if not article_lens_percentages or len(article_lens_percentages) != len(source_labels):
        payload = dict(empty_payload)
        payload["reason"] = "No article-level lens rows available for separation diagnostics."
        return payload

    discovered = {
        lens_name
        for row in article_lens_percentages
        for lens_name, value in row.items()
        if isinstance(lens_name, str) and isinstance(value, (int, float)) and math.isfinite(float(value))
    }
    if preferred_lenses:
        ordered = [lens_name for lens_name in preferred_lenses if lens_name in discovered]
        ordered.extend(sorted(discovered - set(ordered)))
        lens_names = ordered
    else:
        lens_names = sorted(discovered)

    def _complete_matrix(required_lenses: list[str]) -> tuple[list[list[float]], list[str]]:
        matrix: list[list[float]] = []
        labels: list[str] = []
        for row, label in zip(article_lens_percentages, source_labels):
            values: list[float] = []
            for lens_name in required_lenses:
                value = row.get(lens_name)
                if not isinstance(value, (int, float)) or not math.isfinite(float(value)):
                    values = []
                    break
                values.append(float(value))
            if values:
                matrix.append(values)
                labels.append(str(label))
        return matrix, labels

    matrix, matrix_labels = _complete_matrix(lens_names)
    if not matrix and article_lens_percentages:
        shared = set(article_lens_percentages[0].keys())
        for row in article_lens_percentages[1:]:
            shared &= set(row.keys())
        shared = {
            lens_name
            for lens_name in shared
            if isinstance(lens_name, str)
            and all(isinstance(row.get(lens_name), (int, float)) and math.isfinite(float(row[lens_name])) for row in article_lens_percentages)
        }
        if preferred_lenses:
            reduced_lenses = [lens_name for lens_name in preferred_lenses if lens_name in shared]
            reduced_lenses.extend(sorted(shared - set(reduced_lenses)))
        else:
            reduced_lenses = sorted(shared)
        if reduced_lenses:
            lens_names = reduced_lenses
            matrix, matrix_labels = _complete_matrix(lens_names)

    source_counts: Counter[str] = Counter(matrix_labels)
    if not matrix:
        payload = dict(empty_payload)
        payload["reason"] = "Need complete source-lens rows to run separation diagnostics."
        payload["n_lenses"] = len(lens_names)
        payload["source_counts"] = dict(source_counts)
        payload["lenses"] = lens_names
        return payload

    matrix_np = np.asarray(matrix, dtype=float)
    means_np = matrix_np.mean(axis=0)
    centered_np = matrix_np - means_np
    stds_np = centered_np.std(axis=0, ddof=0)
    safe_stds_np = np.where(stds_np > 1e-12, stds_np, 1.0)
    standardized_np = centered_np / safe_stds_np

    n_articles = int(standardized_np.shape[0])
    n_lenses = int(standardized_np.shape[1])
    if n_articles < 2 or n_lenses < 1:
        payload = dict(empty_payload)
        payload["reason"] = "Need at least 2 complete rows and 1 lens to run separation diagnostics."
        payload["n_articles"] = n_articles
        payload["n_lenses"] = n_lenses
        payload["n_sources"] = len(source_counts)
        payload["source_counts"] = dict(source_counts)
        payload["lenses"] = lens_names
        return payload

    source_to_indices: dict[str, list[int]] = defaultdict(list)
    for idx, label in enumerate(matrix_labels):
        source_to_indices[str(label)].append(idx)
    source_names = sorted(source_to_indices.keys())
    n_sources = len(source_names)
    if n_sources < 2:
        payload = dict(empty_payload)
        payload["reason"] = "Need at least 2 sources to evaluate source separation."
        payload["n_articles"] = n_articles
        payload["n_lenses"] = n_lenses
        payload["n_sources"] = n_sources
        payload["source_counts"] = dict(source_counts)
        payload["lenses"] = lens_names
        payload["coverage_mode"] = "complete_rows"
        return payload

    source_centroids_raw: dict[str, Any] = {}
    source_rows: list[dict[str, Any]] = []
    weighted_within_total = 0.0
    weighted_within_n = 0
    for source_name in source_names:
        idxs = source_to_indices[source_name]
        cluster_np = standardized_np[idxs, :]
        centroid_np = cluster_np.mean(axis=0)
        source_centroids_raw[source_name] = centroid_np
        distances = np.sqrt(np.maximum(np.sum((cluster_np - centroid_np) * (cluster_np - centroid_np), axis=1), 0.0))
        within_mean = float(distances.mean()) if len(distances) > 0 else None
        if isinstance(within_mean, float):
            weighted_within_total += within_mean * len(idxs)
            weighted_within_n += len(idxs)
        source_rows.append(
            {
                "source": source_name,
                "count": len(idxs),
                "within_mean_distance": within_mean,
            }
        )
    source_rows.sort(key=lambda row: (-int(row.get("count") or 0), str(row.get("source", "")).lower()))
    within_source_mean_distance = (weighted_within_total / weighted_within_n) if weighted_within_n > 0 else None

    centroid_distances: list[dict[str, Any]] = []
    for row_idx, source_a in enumerate(source_names):
        for col_idx in range(row_idx + 1, len(source_names)):
            source_b = source_names[col_idx]
            centroid_a = source_centroids_raw[source_a]
            centroid_b = source_centroids_raw[source_b]
            distance = float(np.sqrt(np.maximum(np.sum((centroid_a - centroid_b) * (centroid_a - centroid_b)), 0.0)))
            centroid_distances.append(
                {
                    "source_a": source_a,
                    "source_b": source_b,
                    "distance": distance,
                }
            )
    centroid_distances.sort(key=lambda row: float(row.get("distance") or 0.0), reverse=True)
    centroid_distance_values = [float(row["distance"]) for row in centroid_distances if isinstance(row.get("distance"), (int, float))]
    between_source_centroid_mean_distance = (
        (sum(centroid_distance_values) / len(centroid_distance_values)) if centroid_distance_values else None
    )
    between_source_centroid_min_distance = min(centroid_distance_values) if centroid_distance_values else None

    separation_ratio = None
    if isinstance(between_source_centroid_mean_distance, (int, float)) and isinstance(within_source_mean_distance, (int, float)):
        if within_source_mean_distance > 1e-12:
            separation_ratio = float(between_source_centroid_mean_distance) / float(within_source_mean_distance)

    diff_np = standardized_np[:, np.newaxis, :] - standardized_np[np.newaxis, :, :]
    distance_np = np.sqrt(np.maximum(np.sum(diff_np * diff_np, axis=2), 0.0))
    point_silhouette: list[float] = []
    source_silhouette_values: dict[str, list[float]] = defaultdict(list)
    for idx, source_name in enumerate(matrix_labels):
        same_idxs = source_to_indices[source_name]
        a_value = None
        if len(same_idxs) > 1:
            same_without_self = [j for j in same_idxs if j != idx]
            if same_without_self:
                a_value = float(np.mean([distance_np[idx, j] for j in same_without_self]))

        b_candidates: list[float] = []
        for other_source in source_names:
            if other_source == source_name:
                continue
            other_idxs = source_to_indices[other_source]
            if other_idxs:
                b_candidates.append(float(np.mean([distance_np[idx, j] for j in other_idxs])))
        b_value = min(b_candidates) if b_candidates else None
        if isinstance(a_value, (int, float)) and isinstance(b_value, (int, float)):
            denom = max(float(a_value), float(b_value))
            if denom > 1e-12:
                sil = (float(b_value) - float(a_value)) / denom
                point_silhouette.append(sil)
                source_silhouette_values[source_name].append(sil)

    silhouette_like_mean = (sum(point_silhouette) / len(point_silhouette)) if point_silhouette else None
    silhouette_like_by_source = [
        {
            "source": source_name,
            "count": len(values),
            "silhouette_like_mean": (sum(values) / len(values)) if values else None,
        }
        for source_name, values in source_silhouette_values.items()
    ]
    silhouette_like_by_source.sort(key=lambda row: (-int(row.get("count") or 0), str(row.get("source", "")).lower()))

    return {
        "status": "ok",
        "reason": "",
        "n_articles": n_articles,
        "n_lenses": n_lenses,
        "n_sources": n_sources,
        "source_counts": dict(source_counts),
        "lenses": lens_names,
        "basis": "euclidean_distance_on_zscore_lens_percentages",
        "coverage_mode": "complete_rows",
        "within_source_mean_distance": within_source_mean_distance,
        "between_source_centroid_mean_distance": between_source_centroid_mean_distance,
        "between_source_centroid_min_distance": between_source_centroid_min_distance,
        "separation_ratio": separation_ratio,
        "silhouette_like_mean": silhouette_like_mean,
        "silhouette_like_by_source": silhouette_like_by_source,
        "source_centroids": source_rows,
        "centroid_distances": centroid_distances[:25],
    }


def _lens_time_series_from_records(
    records: list[dict[str, Any]],
    lens_maxima: OrderedDict[str, float],
) -> dict[str, Any]:
    if not records:
        return {
            "status": "unavailable",
            "reason": "No records available for lens time series.",
            "basis": "daily_mean_lens_percentages",
            "coverage_mode": "none",
            "lenses": [],
            "dates": [],
            "series": [],
            "summary": {"articles_with_time_and_lens_scores": 0, "days": 0},
        }

    per_day_lens: dict[str, dict[str, list[float]]] = defaultdict(lambda: defaultdict(list))
    article_count = 0
    for record in records:
        published_dt = _record_datetime(record)
        if published_dt is None:
            continue
        lens_percentages = _record_lens_percentages(record, lens_maxima)
        if not lens_percentages:
            continue
        day_key = published_dt.date().isoformat()
        article_count += 1
        for lens_name, lens_value in lens_percentages.items():
            if isinstance(lens_name, str) and isinstance(lens_value, (int, float)) and math.isfinite(float(lens_value)):
                per_day_lens[day_key][lens_name].append(float(lens_value))

    if not per_day_lens:
        return {
            "status": "unavailable",
            "reason": "No records with both valid publication time and lens percentages.",
            "basis": "daily_mean_lens_percentages",
            "coverage_mode": "none",
            "lenses": [],
            "dates": [],
            "series": [],
            "summary": {"articles_with_time_and_lens_scores": 0, "days": 0},
        }

    dates = sorted(per_day_lens.keys())
    discovered_lenses = sorted(
        {
            lens_name
            for day_map in per_day_lens.values()
            for lens_name in day_map.keys()
            if isinstance(lens_name, str)
        }
    )

    preferred = list(lens_maxima.keys())
    ordered_lenses = [lens_name for lens_name in preferred if lens_name in discovered_lenses]
    ordered_lenses.extend([lens_name for lens_name in discovered_lenses if lens_name not in set(ordered_lenses)])

    series: list[dict[str, Any]] = []
    for lens_name in ordered_lenses:
        points: list[dict[str, Any]] = []
        for day_key in dates:
            values = per_day_lens.get(day_key, {}).get(lens_name, [])
            if not values:
                continue
            points.append(
                {
                    "date": day_key,
                    "mean": (sum(values) / len(values)),
                    "median": statistics.median(values),
                    "min": min(values),
                    "max": max(values),
                    "count": len(values),
                }
            )
        series.append({"lens": lens_name, "points": points})

    return {
        "status": "ok",
        "reason": "",
        "basis": "daily_mean_lens_percentages",
        "coverage_mode": "records_with_datetime_and_lens_scores",
        "lenses": ordered_lenses,
        "dates": dates,
        "series": series,
        "summary": {
            "articles_with_time_and_lens_scores": article_count,
            "days": len(dates),
        },
    }


def _source_label_for_record(record: dict[str, Any]) -> str:
    source = record.get("source")
    source_name = None
    if isinstance(source, dict):
        source_name = source.get("name") or source.get("id")
    return _clean_text(source_name) or "Unknown"


def _distribution_rows(
    baseline_counter: Counter[str],
    recent_counter: Counter[str],
    label_key: str,
    *,
    limit: int = 25,
) -> tuple[list[dict[str, Any]], float]:
    baseline_total = sum(int(value) for value in baseline_counter.values())
    recent_total = sum(int(value) for value in recent_counter.values())
    labels = set(baseline_counter.keys()) | set(recent_counter.keys())
    rows: list[dict[str, Any]] = []
    total_variation = 0.0
    for label in labels:
        baseline_count = int(baseline_counter.get(label, 0))
        recent_count = int(recent_counter.get(label, 0))
        baseline_share = (baseline_count / baseline_total) if baseline_total else 0.0
        recent_share = (recent_count / recent_total) if recent_total else 0.0
        share_delta = recent_share - baseline_share
        total_variation += abs(share_delta)
        rows.append(
            {
                label_key: label,
                "baseline_count": baseline_count,
                "recent_count": recent_count,
                "baseline_share": baseline_share,
                "recent_share": recent_share,
                "share_delta": share_delta,
                "abs_share_delta": abs(share_delta),
            }
        )
    rows.sort(key=lambda row: (float(row.get("abs_share_delta") or 0.0), int(row.get("recent_count") or 0)), reverse=True)
    return rows[:limit], total_variation / 2.0


def _drift_diagnostics_from_records(
    records: list[dict[str, Any]],
    lens_maxima: OrderedDict[str, float],
) -> dict[str, Any]:
    dated_records: list[tuple[str, dict[str, Any]]] = []
    for record in records:
        published_dt = _record_datetime(record)
        if published_dt is None:
            continue
        dated_records.append((published_dt.date().isoformat(), record))

    dates = sorted({day for day, _record in dated_records})
    if len(dates) < 2:
        return {
            "status": "unavailable",
            "reason": "Need at least two publication dates to compute drift diagnostics.",
            "basis": "first_half_vs_second_half_by_publication_date",
            "windows": {},
            "lens_drift": [],
            "source_distribution_drift": {"total_variation_distance": None, "rows": []},
            "tag_distribution_drift": {"total_variation_distance": None, "rows": []},
            "volume_drift": {},
            "summary": {"dated_articles": len(dated_records), "days": len(dates)},
        }

    split_index = max(1, len(dates) // 2)
    baseline_dates = set(dates[:split_index])
    recent_dates = set(dates[split_index:])
    if not recent_dates:
        recent_dates = {dates[-1]}
        baseline_dates = set(dates[:-1])

    baseline_lens_values: dict[str, list[float]] = defaultdict(list)
    recent_lens_values: dict[str, list[float]] = defaultdict(list)
    baseline_source_counter: Counter[str] = Counter()
    recent_source_counter: Counter[str] = Counter()
    baseline_tag_counter: Counter[str] = Counter()
    recent_tag_counter: Counter[str] = Counter()
    baseline_daily_counter: Counter[str] = Counter()
    recent_daily_counter: Counter[str] = Counter()

    for day_key, record in dated_records:
        is_recent = day_key in recent_dates
        source_counter = recent_source_counter if is_recent else baseline_source_counter
        tag_counter = recent_tag_counter if is_recent else baseline_tag_counter
        lens_values = recent_lens_values if is_recent else baseline_lens_values
        daily_counter = recent_daily_counter if is_recent else baseline_daily_counter

        source_counter[_source_label_for_record(record)] += 1
        daily_counter[day_key] += 1
        for tag in {tag.strip() for tag in _tag_values_for_record(record) if tag.strip()}:
            tag_counter[tag] += 1
        for lens_name, lens_value in _record_lens_percentages(record, lens_maxima).items():
            if isinstance(lens_name, str) and isinstance(lens_value, (int, float)) and math.isfinite(float(lens_value)):
                lens_values[lens_name].append(float(lens_value))

    discovered_lenses = set(baseline_lens_values.keys()) | set(recent_lens_values.keys())
    ordered_lenses = [lens_name for lens_name in lens_maxima.keys() if lens_name in discovered_lenses]
    ordered_lenses.extend(sorted(discovered_lenses - set(ordered_lenses)))
    lens_rows: list[dict[str, Any]] = []
    for lens_name in ordered_lenses:
        baseline_values = baseline_lens_values.get(lens_name, [])
        recent_values = recent_lens_values.get(lens_name, [])
        baseline_mean = statistics.fmean(baseline_values) if baseline_values else None
        recent_mean = statistics.fmean(recent_values) if recent_values else None
        delta = (
            float(recent_mean) - float(baseline_mean)
            if isinstance(baseline_mean, (int, float)) and isinstance(recent_mean, (int, float))
            else None
        )
        lens_rows.append(
            {
                "lens": lens_name,
                "baseline_mean": baseline_mean,
                "recent_mean": recent_mean,
                "delta": delta,
                "abs_delta": abs(delta) if isinstance(delta, (int, float)) else None,
                "baseline_count": len(baseline_values),
                "recent_count": len(recent_values),
            }
        )
    lens_rows.sort(key=lambda row: float(row.get("abs_delta") or 0.0), reverse=True)

    source_rows, source_tvd = _distribution_rows(baseline_source_counter, recent_source_counter, "source")
    tag_rows, tag_tvd = _distribution_rows(baseline_tag_counter, recent_tag_counter, "tag")
    baseline_daily_values = [int(count) for count in baseline_daily_counter.values()]
    recent_daily_values = [int(count) for count in recent_daily_counter.values()]
    baseline_daily_mean = statistics.fmean(baseline_daily_values) if baseline_daily_values else None
    recent_daily_mean = statistics.fmean(recent_daily_values) if recent_daily_values else None
    volume_delta = (
        float(recent_daily_mean) - float(baseline_daily_mean)
        if isinstance(baseline_daily_mean, (int, float)) and isinstance(recent_daily_mean, (int, float))
        else None
    )
    max_abs_lens_delta = max((float(row.get("abs_delta") or 0.0) for row in lens_rows), default=0.0)
    drift_score = max(source_tvd, tag_tvd, min(max_abs_lens_delta / 100.0, 1.0))
    if drift_score >= 0.25:
        severity = "high"
    elif drift_score >= 0.10:
        severity = "moderate"
    else:
        severity = "low"

    return {
        "status": "ok",
        "reason": "",
        "basis": "first_half_vs_second_half_by_publication_date",
        "windows": {
            "baseline": {
                "start_date": min(baseline_dates) if baseline_dates else None,
                "end_date": max(baseline_dates) if baseline_dates else None,
                "days": len(baseline_dates),
                "articles": sum(baseline_daily_counter.values()),
            },
            "recent": {
                "start_date": min(recent_dates) if recent_dates else None,
                "end_date": max(recent_dates) if recent_dates else None,
                "days": len(recent_dates),
                "articles": sum(recent_daily_counter.values()),
            },
        },
        "lens_drift": lens_rows,
        "source_distribution_drift": {
            "total_variation_distance": source_tvd,
            "rows": source_rows,
        },
        "tag_distribution_drift": {
            "total_variation_distance": tag_tvd,
            "rows": tag_rows,
        },
        "volume_drift": {
            "baseline_daily_mean": baseline_daily_mean,
            "recent_daily_mean": recent_daily_mean,
            "delta_daily_mean": volume_delta,
            "delta_ratio": (volume_delta / baseline_daily_mean) if baseline_daily_mean else None,
        },
        "summary": {
            "dated_articles": len(dated_records),
            "days": len(dates),
            "baseline_articles": sum(baseline_daily_counter.values()),
            "recent_articles": sum(recent_daily_counter.values()),
            "max_abs_lens_delta": max_abs_lens_delta,
            "source_total_variation_distance": source_tvd,
            "tag_total_variation_distance": tag_tvd,
            "drift_score": drift_score,
            "severity": severity,
        },
    }


def _latent_space_stability_from_records(
    article_lens_percentages: list[dict[str, float]],
    source_labels: list[str],
    article_meta_rows: list[dict[str, Any]],
    full_pca: dict[str, Any],
    preferred_lenses: list[str] | None = None,
    *,
    resamples: int = 12,
    sample_fraction: float = 0.8,
    seed: int = 42,
) -> dict[str, Any]:
    if str(full_pca.get("status") or "") != "ok":
        return {
            "status": "unavailable",
            "reason": "Full PCA is unavailable; latent stability cannot be computed.",
            "basis": "deterministic_subsample_pca",
            "config": {"resamples": resamples, "sample_fraction": sample_fraction, "seed": seed},
            "components": [],
            "loading_stability": [],
            "summary": {"stable_component_count": 0, "component_count": 0, "resamples_completed": 0},
        }

    if len(article_lens_percentages) < 6 or len(article_lens_percentages) != len(source_labels):
        return {
            "status": "unavailable",
            "reason": "Need at least 6 aligned article lens rows for latent stability.",
            "basis": "deterministic_subsample_pca",
            "config": {"resamples": resamples, "sample_fraction": sample_fraction, "seed": seed},
            "components": [],
            "loading_stability": [],
            "summary": {"stable_component_count": 0, "component_count": 0, "resamples_completed": 0},
        }

    full_loadings = full_pca.get("loadings")
    if not isinstance(full_loadings, dict):
        return {
            "status": "unavailable",
            "reason": "Full PCA loadings are missing.",
            "basis": "deterministic_subsample_pca",
            "config": {"resamples": resamples, "sample_fraction": sample_fraction, "seed": seed},
            "components": [],
            "loading_stability": [],
            "summary": {"stable_component_count": 0, "component_count": 0, "resamples_completed": 0},
        }

    full_lenses = [str(lens) for lens in full_loadings.get("lenses", []) if isinstance(lens, str)]
    full_components = [str(component) for component in full_loadings.get("components", []) if isinstance(component, str)]
    full_matrix = full_loadings.get("matrix")
    if not full_lenses or not full_components or not isinstance(full_matrix, list):
        return {
            "status": "unavailable",
            "reason": "Full PCA loading matrix is incomplete.",
            "basis": "deterministic_subsample_pca",
            "config": {"resamples": resamples, "sample_fraction": sample_fraction, "seed": seed},
            "components": [],
            "loading_stability": [],
            "summary": {"stable_component_count": 0, "component_count": 0, "resamples_completed": 0},
        }

    component_labels = full_components[: min(2, len(full_components))]
    full_vectors: dict[str, list[float]] = {}
    for component_index, component_label in enumerate(component_labels):
        row = full_matrix[component_index] if component_index < len(full_matrix) and isinstance(full_matrix[component_index], list) else []
        vector = []
        for value in row[: len(full_lenses)]:
            coerced = _coerce_float(value)
            vector.append(float(coerced) if coerced is not None else 0.0)
        if len(vector) == len(full_lenses):
            full_vectors[component_label] = vector

    if not full_vectors:
        return {
            "status": "unavailable",
            "reason": "No comparable full PCA component vectors were available.",
            "basis": "deterministic_subsample_pca",
            "config": {"resamples": resamples, "sample_fraction": sample_fraction, "seed": seed},
            "components": [],
            "loading_stability": [],
            "summary": {"stable_component_count": 0, "component_count": 0, "resamples_completed": 0},
        }

    sample_size = max(4, min(len(article_lens_percentages) - 1, int(round(len(article_lens_percentages) * sample_fraction))))
    component_cosines: dict[str, list[float]] = defaultdict(list)
    component_explained: dict[str, list[float]] = defaultdict(list)
    loading_samples: dict[str, dict[str, list[float]]] = defaultdict(lambda: defaultdict(list))
    completed = 0

    for resample_index in range(max(1, resamples)):
        rng = random.Random(seed + resample_index)
        sample_indexes = sorted(rng.sample(range(len(article_lens_percentages)), sample_size))
        sample_lens_rows = [article_lens_percentages[index] for index in sample_indexes]
        sample_sources = [source_labels[index] for index in sample_indexes]
        sample_meta = [
            article_meta_rows[index] if index < len(article_meta_rows) and isinstance(article_meta_rows[index], dict) else {}
            for index in sample_indexes
        ]
        sample_pca = _lens_pca_from_records(
            sample_lens_rows,
            sample_sources,
            article_meta_rows=sample_meta,
            preferred_lenses=preferred_lenses,
            max_components=2,
        )
        if str(sample_pca.get("status") or "") != "ok":
            continue
        sample_loadings = sample_pca.get("loadings")
        if not isinstance(sample_loadings, dict):
            continue
        sample_lenses = [str(lens) for lens in sample_loadings.get("lenses", []) if isinstance(lens, str)]
        sample_matrix = sample_loadings.get("matrix")
        if not sample_lenses or not isinstance(sample_matrix, list):
            continue
        sample_lens_index = {lens: idx for idx, lens in enumerate(sample_lenses)}
        explained_by_component = {
            str(row.get("component") or ""): _coerce_float(row.get("explained_variance_ratio"))
            for row in sample_pca.get("explained_variance", [])
            if isinstance(row, dict)
        }
        completed += 1
        for component_index, component_label in enumerate(component_labels):
            if component_label not in full_vectors or component_index >= len(sample_matrix) or not isinstance(sample_matrix[component_index], list):
                continue
            sample_vector: list[float] = []
            for lens_name in full_lenses:
                sample_index = sample_lens_index.get(lens_name)
                value = sample_matrix[component_index][sample_index] if sample_index is not None and sample_index < len(sample_matrix[component_index]) else 0.0
                coerced = _coerce_float(value)
                sample_vector.append(float(coerced) if coerced is not None else 0.0)
            full_vector = full_vectors[component_label]
            dot = sum(a * b for a, b in zip(full_vector, sample_vector))
            if dot < 0:
                sample_vector = [-value for value in sample_vector]
                dot = -dot
            full_norm = math.sqrt(sum(value * value for value in full_vector))
            sample_norm = math.sqrt(sum(value * value for value in sample_vector))
            cosine = dot / (full_norm * sample_norm) if full_norm > 0 and sample_norm > 0 else None
            if cosine is not None:
                component_cosines[component_label].append(cosine)
            explained = explained_by_component.get(component_label)
            if explained is not None:
                component_explained[component_label].append(float(explained))
            for lens_name, loading in zip(full_lenses, sample_vector):
                loading_samples[lens_name][component_label].append(float(loading))

    component_rows: list[dict[str, Any]] = []
    stable_count = 0
    for component_label in component_labels:
        cosines = component_cosines.get(component_label, [])
        explained_values = component_explained.get(component_label, [])
        mean_cosine = statistics.fmean(cosines) if cosines else None
        min_cosine = min(cosines) if cosines else None
        explained_mean = statistics.fmean(explained_values) if explained_values else None
        explained_stddev = statistics.pstdev(explained_values) if len(explained_values) > 1 else 0.0 if explained_values else None
        stable = bool(mean_cosine is not None and mean_cosine >= 0.9 and (min_cosine is None or min_cosine >= 0.75))
        if stable:
            stable_count += 1
        component_rows.append(
            {
                "component": component_label,
                "resamples": len(cosines),
                "mean_cosine_similarity": mean_cosine,
                "min_cosine_similarity": min_cosine,
                "explained_variance_mean": explained_mean,
                "explained_variance_stddev": explained_stddev,
                "stable": stable,
            }
        )

    loading_rows: list[dict[str, Any]] = []
    for lens_name in full_lenses:
        row: dict[str, Any] = {"lens": lens_name}
        max_stddev = 0.0
        for component_label in component_labels:
            samples = loading_samples[lens_name].get(component_label, [])
            mean_value = statistics.fmean(samples) if samples else None
            stddev_value = statistics.pstdev(samples) if len(samples) > 1 else 0.0 if samples else None
            row[f"{component_label.lower()}_loading_mean"] = mean_value
            row[f"{component_label.lower()}_loading_stddev"] = stddev_value
            if isinstance(stddev_value, (int, float)):
                max_stddev = max(max_stddev, float(stddev_value))
        row["max_loading_stddev"] = max_stddev
        loading_rows.append(row)
    loading_rows.sort(key=lambda row: float(row.get("max_loading_stddev") or 0.0), reverse=True)

    return {
        "status": "ok" if completed else "unavailable",
        "reason": "" if completed else "No PCA resamples completed successfully.",
        "basis": "deterministic_subsample_pca",
        "config": {
            "resamples": resamples,
            "sample_fraction": sample_fraction,
            "sample_size": sample_size,
            "seed": seed,
        },
        "components": component_rows,
        "loading_stability": loading_rows,
        "summary": {
            "stable_component_count": stable_count,
            "component_count": len(component_rows),
            "resamples_completed": completed,
            "mean_component_similarity": statistics.fmean(
                [float(row["mean_cosine_similarity"]) for row in component_rows if isinstance(row.get("mean_cosine_similarity"), (int, float))]
            )
            if any(isinstance(row.get("mean_cosine_similarity"), (int, float)) for row in component_rows)
            else None,
            "most_unstable_lens": loading_rows[0].get("lens") if loading_rows else None,
            "max_loading_stddev": loading_rows[0].get("max_loading_stddev") if loading_rows else None,
        },
    }


def _lens_temporal_embedding_from_pca(pca_payload: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(pca_payload, dict):
        return {
            "status": "unavailable",
            "reason": "PCA payload missing.",
            "basis": "pc1_pc2_with_day_index",
            "coverage_mode": "none",
            "points": [],
            "day_centroids": [],
            "summary": {"articles": 0, "days": 0},
        }

    if str(pca_payload.get("status") or "") != "ok":
        reason = str(pca_payload.get("reason") or "").strip() or "PCA is unavailable."
        return {
            "status": "unavailable",
            "reason": reason,
            "basis": "pc1_pc2_with_day_index",
            "coverage_mode": "none",
            "points": [],
            "day_centroids": [],
            "summary": {"articles": 0, "days": 0},
        }

    article_points = pca_payload.get("article_points")
    if not isinstance(article_points, list):
        return {
            "status": "unavailable",
            "reason": "PCA article points are missing.",
            "basis": "pc1_pc2_with_day_index",
            "coverage_mode": "none",
            "points": [],
            "day_centroids": [],
            "summary": {"articles": 0, "days": 0},
        }

    valid_rows: list[dict[str, Any]] = []
    for row in article_points:
        if not isinstance(row, dict):
            continue
        pc1 = row.get("pc1")
        pc2 = row.get("pc2")
        published_at = row.get("published_at")
        if not isinstance(pc1, (int, float)) or not isinstance(pc2, (int, float)):
            continue
        dt = parse_datetime(published_at)
        if dt is None:
            continue
        valid_rows.append(
            {
                "id": _clean_text(row.get("id")),
                "title": _clean_text(row.get("title")) or "Untitled",
                "source": _clean_text(row.get("source")) or "Unknown",
                "strongest_lens": _clean_text(row.get("strongest_lens")) or "Unknown",
                "strongest_percent": _coerce_float(row.get("strongest_percent")),
                "published_at": _as_iso_utc(dt),
                "date": dt.date().isoformat(),
                "pc1": float(pc1),
                "pc2": float(pc2),
            }
        )

    if not valid_rows:
        return {
            "status": "unavailable",
            "reason": "No PCA article points have valid publication timestamps.",
            "basis": "pc1_pc2_with_day_index",
            "coverage_mode": "none",
            "points": [],
            "day_centroids": [],
            "summary": {"articles": 0, "days": 0},
        }

    day_values = sorted({row["date"] for row in valid_rows if isinstance(row.get("date"), str)})
    day_index_map = {day: idx for idx, day in enumerate(day_values)}
    day_groups: dict[str, list[dict[str, Any]]] = defaultdict(list)

    points: list[dict[str, Any]] = []
    for row in valid_rows:
        day = row["date"]
        day_index = day_index_map.get(day)
        if day_index is None:
            continue
        enriched = dict(row)
        enriched["day_index"] = day_index
        points.append(enriched)
        day_groups[day].append(enriched)

    day_centroids: list[dict[str, Any]] = []
    for day in day_values:
        rows = day_groups.get(day, [])
        if not rows:
            continue
        day_centroids.append(
            {
                "date": day,
                "day_index": day_index_map[day],
                "count": len(rows),
                "pc1": sum(float(row["pc1"]) for row in rows) / len(rows),
                "pc2": sum(float(row["pc2"]) for row in rows) / len(rows),
            }
        )

    return {
        "status": "ok",
        "reason": "",
        "basis": "pc1_pc2_with_day_index",
        "coverage_mode": "pca_points_with_datetime",
        "points": points,
        "day_centroids": day_centroids,
        "summary": {
            "articles": len(points),
            "days": len(day_centroids),
            "start_date": day_values[0] if day_values else None,
            "end_date": day_values[-1] if day_values else None,
        },
    }


def _lens_temporal_embedding_from_mds(mds_payload: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(mds_payload, dict):
        return {
            "status": "unavailable",
            "reason": "MDS payload missing.",
            "basis": "mds1_mds2_with_day_index",
            "coverage_mode": "none",
            "points": [],
            "day_centroids": [],
            "summary": {"articles": 0, "days": 0},
        }

    if str(mds_payload.get("status") or "") != "ok":
        reason = str(mds_payload.get("reason") or "").strip() or "MDS is unavailable."
        return {
            "status": "unavailable",
            "reason": reason,
            "basis": "mds1_mds2_with_day_index",
            "coverage_mode": "none",
            "points": [],
            "day_centroids": [],
            "summary": {"articles": 0, "days": 0},
        }

    article_points = mds_payload.get("article_points")
    if not isinstance(article_points, list):
        return {
            "status": "unavailable",
            "reason": "MDS article points are missing.",
            "basis": "mds1_mds2_with_day_index",
            "coverage_mode": "none",
            "points": [],
            "day_centroids": [],
            "summary": {"articles": 0, "days": 0},
        }

    valid_rows: list[dict[str, Any]] = []
    for row in article_points:
        if not isinstance(row, dict):
            continue
        mds1 = row.get("mds1")
        mds2 = row.get("mds2")
        published_at = row.get("published_at")
        if not isinstance(mds1, (int, float)) or not isinstance(mds2, (int, float)):
            continue
        dt = parse_datetime(published_at)
        if dt is None:
            continue
        valid_rows.append(
            {
                "id": _clean_text(row.get("id")),
                "title": _clean_text(row.get("title")) or "Untitled",
                "source": _clean_text(row.get("source")) or "Unknown",
                "strongest_lens": _clean_text(row.get("strongest_lens")) or "Unknown",
                "strongest_percent": _coerce_float(row.get("strongest_percent")),
                "published_at": _as_iso_utc(dt),
                "date": dt.date().isoformat(),
                "mds1": float(mds1),
                "mds2": float(mds2),
            }
        )

    if not valid_rows:
        return {
            "status": "unavailable",
            "reason": "No MDS article points have valid publication timestamps.",
            "basis": "mds1_mds2_with_day_index",
            "coverage_mode": "none",
            "points": [],
            "day_centroids": [],
            "summary": {"articles": 0, "days": 0},
        }

    day_values = sorted({row["date"] for row in valid_rows if isinstance(row.get("date"), str)})
    day_index_map = {day: idx for idx, day in enumerate(day_values)}
    day_groups: dict[str, list[dict[str, Any]]] = defaultdict(list)

    points: list[dict[str, Any]] = []
    for row in valid_rows:
        day = row["date"]
        day_index = day_index_map.get(day)
        if day_index is None:
            continue
        enriched = dict(row)
        enriched["day_index"] = day_index
        points.append(enriched)
        day_groups[day].append(enriched)

    day_centroids: list[dict[str, Any]] = []
    for day in day_values:
        rows = day_groups.get(day, [])
        if not rows:
            continue
        day_centroids.append(
            {
                "date": day,
                "day_index": day_index_map[day],
                "count": len(rows),
                "mds1": sum(float(row["mds1"]) for row in rows) / len(rows),
                "mds2": sum(float(row["mds2"]) for row in rows) / len(rows),
            }
        )

    return {
        "status": "ok",
        "reason": "",
        "basis": "mds1_mds2_with_day_index",
        "coverage_mode": "mds_points_with_datetime",
        "points": points,
        "day_centroids": day_centroids,
        "summary": {
            "articles": len(points),
            "days": len(day_centroids),
            "start_date": day_values[0] if day_values else None,
            "end_date": day_values[-1] if day_values else None,
        },
    }


def _oneway_source_effect(
    values: list[float],
    source_labels: list[str],
) -> dict[str, Any] | None:
    if not values or len(values) != len(source_labels):
        return None

    by_source: dict[str, list[float]] = {}
    for value, label in zip(values, source_labels):
        by_source.setdefault(label, []).append(value)

    n = len(values)
    k = len(by_source)
    if k < 2 or n <= k:
        return None

    grand_mean = sum(values) / n
    source_means: dict[str, float] = {}
    source_counts: dict[str, int] = {}
    ss_between = 0.0
    ss_within = 0.0
    for source_name, group_values in by_source.items():
        if not group_values:
            continue
        group_count = len(group_values)
        group_mean = sum(group_values) / group_count
        source_means[source_name] = group_mean
        source_counts[source_name] = group_count
        ss_between += group_count * (group_mean - grand_mean) ** 2
        ss_within += sum((value - group_mean) ** 2 for value in group_values)

    if len(source_means) < 2:
        return None

    df_between = len(source_means) - 1
    df_within = n - len(source_means)
    if df_between <= 0 or df_within <= 0:
        return None

    ms_between = ss_between / df_between
    ms_within = ss_within / df_within
    if ms_within <= 0:
        ms_within = 1e-12
    f_stat = ms_between / ms_within

    ss_total = ss_between + ss_within
    eta_sq = (ss_between / ss_total) if ss_total > 0 else 0.0
    return {
        "f_stat": f_stat,
        "eta_sq": eta_sq,
        "df_between": df_between,
        "df_within": df_within,
        "n": n,
        "source_means": source_means,
        "source_counts": source_counts,
    }


def _permutation_pvalue_for_source_effect(
    observed_f: float | None,
    values: list[float],
    source_labels: list[str],
    permutations: int,
    seed: int,
) -> float | None:
    if observed_f is None or permutations <= 0:
        return None

    permuted_labels = source_labels.copy()
    rng = random.Random(seed)
    extreme = 0
    valid = 0
    for _ in range(permutations):
        rng.shuffle(permuted_labels)
        result = _oneway_source_effect(values, permuted_labels)
        if not isinstance(result, dict):
            continue
        f_stat = _coerce_float(result.get("f_stat"))
        if f_stat is None:
            continue
        valid += 1
        if f_stat >= observed_f - 1e-12:
            extreme += 1

    if valid == 0:
        return None
    return (extreme + 1) / (valid + 1)


def _benjamini_hochberg_adjust(p_values: list[float | None]) -> list[float | None]:
    """Return Benjamini-Hochberg FDR-adjusted p-values, preserving input order."""
    indexed: list[tuple[int, float]] = []
    for idx, raw in enumerate(p_values):
        if isinstance(raw, (int, float)):
            value = float(raw)
            if math.isfinite(value):
                indexed.append((idx, min(max(value, 0.0), 1.0)))

    adjusted: list[float | None] = [None] * len(p_values)
    m = len(indexed)
    if m == 0:
        return adjusted

    indexed.sort(key=lambda item: item[1])
    running_min = 1.0
    for rank, (orig_idx, p_value) in enumerate(reversed(indexed), start=1):
        i = m - rank + 1
        candidate = (p_value * m) / i
        running_min = min(running_min, candidate)
        adjusted[orig_idx] = min(max(running_min, 0.0), 1.0)
    return adjusted


def _source_lens_effects_from_records(
    article_lens_percentages: list[dict[str, float]],
    source_labels: list[str],
    preferred_lenses: list[str] | None = None,
    permutations: int = _SOURCE_EFFECT_PERMUTATIONS,
    random_seed: int = _SOURCE_EFFECT_RANDOM_SEED,
) -> dict[str, Any]:
    if not article_lens_percentages or len(article_lens_percentages) != len(source_labels):
        return {
            "status": "unavailable",
            "reason": "No article-level lens rows available.",
            "permutations": permutations,
            "multiple_testing": {
                "method": "benjamini-hochberg",
                "target": "p_perm_raw",
                "n_tests": 0,
            },
            "rows": [],
        }

    discovered_lenses = {
        lens_name
        for row in article_lens_percentages
        for lens_name, value in row.items()
        if isinstance(lens_name, str) and isinstance(value, (int, float))
    }
    if preferred_lenses:
        ordered = [lens_name for lens_name in preferred_lenses if lens_name in discovered_lenses]
        ordered.extend(sorted(discovered_lenses - set(ordered)))
        lens_names = ordered
    else:
        lens_names = sorted(discovered_lenses)

    rows: list[dict[str, Any]] = []
    for lens_index, lens_name in enumerate(lens_names):
        values: list[float] = []
        labels: list[str] = []
        for row, source_label in zip(article_lens_percentages, source_labels):
            value = row.get(lens_name)
            if isinstance(value, (int, float)):
                values.append(float(value))
                labels.append(source_label)

        effect = _oneway_source_effect(values, labels)
        if not isinstance(effect, dict):
            continue

        observed_f = _coerce_float(effect.get("f_stat"))
        p_perm = _permutation_pvalue_for_source_effect(
            observed_f=observed_f,
            values=values,
            source_labels=labels,
            permutations=permutations,
            seed=random_seed + lens_index,
        )

        source_means = effect.get("source_means") if isinstance(effect.get("source_means"), dict) else {}
        sorted_sources = sorted(
            ((str(name), float(mean)) for name, mean in source_means.items() if isinstance(mean, (int, float))),
            key=lambda item: item[1],
        )
        low_source = sorted_sources[0][0] if sorted_sources else None
        high_source = sorted_sources[-1][0] if sorted_sources else None
        source_gap = (sorted_sources[-1][1] - sorted_sources[0][1]) if len(sorted_sources) >= 2 else 0.0

        source_counts = effect.get("source_counts") if isinstance(effect.get("source_counts"), dict) else {}

        rows.append(
            {
                "lens": lens_name,
                "n": int(effect.get("n", 0)),
                "n_sources": len(source_counts),
                "df_between": int(effect.get("df_between", 0)),
                "df_within": int(effect.get("df_within", 0)),
                "f_stat": observed_f,
                "eta_sq": _coerce_float(effect.get("eta_sq")),
                "p_perm": p_perm,
                "p_perm_raw": p_perm,
                "source_gap": source_gap,
                "top_source": high_source,
                "bottom_source": low_source,
                "source_means": source_means,
                "source_counts": source_counts,
            }
        )

    adjusted_p_values = _benjamini_hochberg_adjust([_coerce_float(row.get("p_perm_raw")) for row in rows])
    for row, p_fdr in zip(rows, adjusted_p_values):
        p_raw = _coerce_float(row.get("p_perm_raw"))
        row["p_value_raw"] = p_raw
        row["p_value_fdr"] = p_fdr
        row["p_perm_fdr"] = p_fdr
        row["significant_fdr_0_05"] = bool(isinstance(p_fdr, (int, float)) and float(p_fdr) <= 0.05)

    rows.sort(
        key=lambda row: (
            1.0 if row.get("p_perm") is None else float(row.get("p_perm")),
            -1.0 if row.get("eta_sq") is None else -float(row.get("eta_sq")),
            str(row.get("lens", "")).lower(),
        )
    )

    if rows:
        return {
            "status": "ok",
            "reason": "",
            "permutations": permutations,
            "multiple_testing": {
                "method": "benjamini-hochberg",
                "target": "p_perm_raw",
                "n_tests": sum(1 for row in rows if isinstance(row.get("p_perm_raw"), (int, float))),
            },
            "rows": rows,
        }
    return {
        "status": "unavailable",
        "reason": "Insufficient source coverage for one-way lens tests.",
        "permutations": permutations,
        "multiple_testing": {
            "method": "benjamini-hochberg",
            "target": "p_perm_raw",
            "n_tests": 0,
        },
        "rows": [],
    }


def _multivariate_source_separation(
    matrix: list[list[float]],
    source_labels: list[str],
) -> dict[str, Any] | None:
    if not matrix or len(matrix) != len(source_labels):
        return None
    dims = len(matrix[0])
    if dims == 0:
        return None
    if any(len(row) != dims for row in matrix):
        return None

    n = len(matrix)
    by_source: dict[str, list[int]] = {}
    for row_index, label in enumerate(source_labels):
        by_source.setdefault(label, []).append(row_index)

    k = len(by_source)
    if k < 2 or n <= k:
        return None

    grand_mean = [0.0 for _ in range(dims)]
    for row in matrix:
        for dim_idx, value in enumerate(row):
            grand_mean[dim_idx] += value
    grand_mean = [value / n for value in grand_mean]

    ss_total = 0.0
    for row in matrix:
        ss_total += sum((value - grand_mean[dim_idx]) ** 2 for dim_idx, value in enumerate(row))

    ss_within = 0.0
    for row_indexes in by_source.values():
        group_size = len(row_indexes)
        if group_size == 0:
            continue
        group_mean = [0.0 for _ in range(dims)]
        for row_index in row_indexes:
            row = matrix[row_index]
            for dim_idx, value in enumerate(row):
                group_mean[dim_idx] += value
        group_mean = [value / group_size for value in group_mean]

        for row_index in row_indexes:
            row = matrix[row_index]
            ss_within += sum((value - group_mean[dim_idx]) ** 2 for dim_idx, value in enumerate(row))

    ss_between = max(0.0, ss_total - ss_within)
    df_between = k - 1
    df_within = n - k
    if df_between <= 0 or df_within <= 0:
        return None

    ms_between = ss_between / df_between
    ms_within = ss_within / df_within
    if ms_within <= 0:
        ms_within = 1e-12

    f_stat = ms_between / ms_within
    r_squared = (ss_between / ss_total) if ss_total > 0 else 0.0
    return {
        "f_stat": f_stat,
        "r_squared": r_squared,
        "df_between": df_between,
        "df_within": df_within,
    }


def _nearest_centroid_loocv(
    matrix: list[list[float]],
    source_labels: list[str],
) -> dict[str, Any] | None:
    if not matrix or len(matrix) != len(source_labels):
        return None
    dims = len(matrix[0])
    if dims == 0:
        return None
    if any(len(row) != dims for row in matrix):
        return None

    n = len(matrix)
    unique_sources = sorted(set(source_labels))
    if len(unique_sources) < 2:
        return None

    correct = 0
    evaluated = 0
    for holdout_index in range(n):
        sums: dict[str, list[float]] = {}
        counts: dict[str, int] = {}
        for row_index, row in enumerate(matrix):
            if row_index == holdout_index:
                continue
            label = source_labels[row_index]
            sums.setdefault(label, [0.0 for _ in range(dims)])
            counts[label] = counts.get(label, 0) + 1
            for dim_idx, value in enumerate(row):
                sums[label][dim_idx] += value

        centroids: dict[str, list[float]] = {}
        for label, vector_sums in sums.items():
            count = counts.get(label, 0)
            if count <= 0:
                continue
            centroids[label] = [value / count for value in vector_sums]

        true_label = source_labels[holdout_index]
        if true_label not in centroids:
            continue

        row = matrix[holdout_index]
        best_label = ""
        best_distance = float("inf")
        for label, centroid in centroids.items():
            distance = sum((value - centroid[dim_idx]) ** 2 for dim_idx, value in enumerate(row))
            if distance < best_distance:
                best_distance = distance
                best_label = label

        evaluated += 1
        if best_label == true_label:
            correct += 1

    if evaluated == 0:
        return None

    source_counts: Counter[str] = Counter(source_labels)
    baseline_accuracy = (max(source_counts.values()) / n) if n else 0.0
    accuracy = correct / evaluated
    return {
        "accuracy": accuracy,
        "baseline_accuracy": baseline_accuracy,
        "evaluated": evaluated,
        "total": n,
    }


def _permutation_pvalue(
    observed: float | None,
    source_labels: list[str],
    permutations: int,
    seed: int,
    stat_fn,
) -> float | None:
    if observed is None or permutations <= 0:
        return None

    rng = random.Random(seed)
    permuted_labels = source_labels.copy()
    extreme = 0
    valid = 0
    for _ in range(permutations):
        rng.shuffle(permuted_labels)
        permuted_value = stat_fn(permuted_labels)
        if not isinstance(permuted_value, (int, float)):
            continue
        valid += 1
        if float(permuted_value) >= observed - 1e-12:
            extreme += 1

    if valid == 0:
        return None
    return (extreme + 1) / (valid + 1)


def _source_differentiation_from_records(
    article_lens_percentages: list[dict[str, float]],
    source_labels: list[str],
    preferred_lenses: list[str] | None = None,
    permutations: int = _SOURCE_EFFECT_PERMUTATIONS,
    random_seed: int = _SOURCE_EFFECT_RANDOM_SEED,
) -> dict[str, Any]:
    if not article_lens_percentages or len(article_lens_percentages) != len(source_labels):
        return {
            "status": "unavailable",
            "reason": "No article-level lens rows available for source tests.",
            "n_articles": 0,
            "n_sources": 0,
            "n_lenses": 0,
            "source_counts": {},
            "permutations": permutations,
            "multivariate": None,
            "classification": None,
        }

    discovered_lenses = {
        lens_name
        for row in article_lens_percentages
        for lens_name, value in row.items()
        if isinstance(lens_name, str) and isinstance(value, (int, float))
    }
    if preferred_lenses:
        ordered = [lens_name for lens_name in preferred_lenses if lens_name in discovered_lenses]
        ordered.extend(sorted(discovered_lenses - set(ordered)))
        lens_names = ordered
    else:
        lens_names = sorted(discovered_lenses)

    def _complete_matrix(required_lenses: list[str]) -> tuple[list[list[float]], list[str]]:
        matrix: list[list[float]] = []
        labels: list[str] = []
        for row, label in zip(article_lens_percentages, source_labels):
            values: list[float] = []
            for lens_name in required_lenses:
                value = row.get(lens_name)
                if not isinstance(value, (int, float)):
                    values = []
                    break
                values.append(float(value))
            if values:
                matrix.append(values)
                labels.append(label)
        return matrix, labels

    matrix, matrix_labels = _complete_matrix(lens_names)
    if not matrix:
        if article_lens_percentages:
            shared = set(article_lens_percentages[0].keys())
            for row in article_lens_percentages[1:]:
                shared &= set(row.keys())
            if preferred_lenses:
                reduced_lenses = [lens_name for lens_name in preferred_lenses if lens_name in shared]
                reduced_lenses.extend(sorted(shared - set(reduced_lenses)))
            else:
                reduced_lenses = sorted(shared)
            if reduced_lenses:
                lens_names = reduced_lenses
                matrix, matrix_labels = _complete_matrix(lens_names)

    source_counts: Counter[str] = Counter(matrix_labels)
    summary: dict[str, Any] = {
        "status": "unavailable",
        "reason": "",
        "n_articles": len(matrix),
        "n_sources": len(source_counts),
        "n_lenses": len(lens_names),
        "source_counts": dict(source_counts),
        "permutations": permutations,
        "multivariate": None,
        "classification": None,
    }

    if not matrix:
        summary["reason"] = "Need complete source-lens rows to run source differentiation tests."
        return summary
    if len(source_counts) < 2:
        summary["reason"] = "Need at least 2 sources with complete rows."
        return summary
    if len(lens_names) < 1:
        summary["reason"] = "Need at least 1 lens with complete source coverage."
        return summary

    multivariate = _multivariate_source_separation(matrix, matrix_labels)
    if isinstance(multivariate, dict):
        observed_f = _coerce_float(multivariate.get("f_stat"))
        multivariate["p_perm"] = _permutation_pvalue(
            observed=observed_f,
            source_labels=matrix_labels,
            permutations=permutations,
            seed=random_seed,
            stat_fn=lambda labels: (
                (_multivariate_source_separation(matrix, labels) or {}).get("f_stat")
            ),
        )
        summary["multivariate"] = multivariate

    classification = _nearest_centroid_loocv(matrix, matrix_labels)
    if isinstance(classification, dict):
        observed_accuracy = _coerce_float(classification.get("accuracy"))
        classification["p_perm"] = _permutation_pvalue(
            observed=observed_accuracy,
            source_labels=matrix_labels,
            permutations=permutations,
            seed=random_seed + 1,
            stat_fn=lambda labels: ((_nearest_centroid_loocv(matrix, labels) or {}).get("accuracy")),
        )
        summary["classification"] = classification

    if summary["multivariate"] or summary["classification"]:
        summary["status"] = "ok"
    else:
        summary["reason"] = "Insufficient degrees of freedom for source-level tests."
    return summary


def _topic_memberships_from_record(
    record: dict[str, Any],
    topic_display_labels: dict[str, str],
) -> list[str]:
    topic_values = _unique_case_insensitive(_values_to_strings(record.get("topic_tags")))
    topic_keys: list[str] = []
    for topic_value in topic_values:
        topic_text = topic_value.strip()
        if not topic_text:
            continue
        topic_key = topic_text.lower()
        if topic_key not in topic_display_labels:
            topic_display_labels[topic_key] = topic_text
        topic_keys.append(topic_key)

    if topic_keys:
        return topic_keys

    topic_display_labels.setdefault("__untagged__", "Untagged")
    return ["__untagged__"]


def _source_topic_control_from_records(
    article_lens_percentages: list[dict[str, float]],
    source_labels: list[str],
    topic_keys_for_lens_rows: list[list[str]],
    topic_display_labels: dict[str, str],
    pooled_source_differentiation: dict[str, Any],
    pooled_source_lens_effects: dict[str, Any],
    preferred_lenses: list[str] | None = None,
) -> dict[str, Any]:
    base_payload: dict[str, Any] = {
        "topic_basis": "topic_tags",
        "multi_topic_policy": "duplicate_per_topic",
        "pooled_label": "topic-confounded",
        "pooled": {
            "source_differentiation": (
                pooled_source_differentiation if isinstance(pooled_source_differentiation, dict) else {}
            ),
            "source_lens_effects": pooled_source_lens_effects if isinstance(pooled_source_lens_effects, dict) else {},
        },
        "topics": [],
        "summary": {
            "topic_count": 0,
            "analyzed_topic_count": 0,
            "unavailable_topic_count": 0,
        },
    }
    if (
        not article_lens_percentages
        or len(article_lens_percentages) != len(source_labels)
        or len(article_lens_percentages) != len(topic_keys_for_lens_rows)
    ):
        return base_payload

    topic_display = dict(topic_display_labels)
    topic_display.setdefault("__untagged__", "Untagged")

    topic_buckets: dict[str, dict[str, Any]] = defaultdict(lambda: {"rows": [], "source_labels": []})
    for lens_row, source_label, topic_keys in zip(
        article_lens_percentages,
        source_labels,
        topic_keys_for_lens_rows,
    ):
        effective_keys: list[str] = []
        if isinstance(topic_keys, list):
            for topic_key in topic_keys:
                if not isinstance(topic_key, str):
                    continue
                normalized_key = topic_key.strip().lower()
                if not normalized_key:
                    continue
                effective_keys.append(normalized_key)
        if not effective_keys:
            effective_keys = ["__untagged__"]

        unique_keys = list(dict.fromkeys(effective_keys))
        for topic_key in unique_keys:
            topic_buckets[topic_key]["rows"].append(lens_row)
            topic_buckets[topic_key]["source_labels"].append(source_label)

    topic_rows: list[dict[str, Any]] = []
    analyzed_topic_count = 0
    unavailable_topic_count = 0
    for topic_key, bucket in topic_buckets.items():
        topic_rows_data = bucket["rows"] if isinstance(bucket.get("rows"), list) else []
        topic_source_labels = bucket["source_labels"] if isinstance(bucket.get("source_labels"), list) else []
        source_counts_counter: Counter[str] = Counter(topic_source_labels)
        source_counts = {
            source_name: count
            for source_name, count in sorted(
                source_counts_counter.items(),
                key=lambda item: (-item[1], item[0].lower()),
            )
        }

        topic_source_lens_effects = _source_lens_effects_from_records(
            topic_rows_data,
            topic_source_labels,
            preferred_lenses=preferred_lenses,
        )
        topic_source_differentiation = _source_differentiation_from_records(
            topic_rows_data,
            topic_source_labels,
            preferred_lenses=preferred_lenses,
        )

        differentiation_ok = (
            isinstance(topic_source_differentiation, dict)
            and str(topic_source_differentiation.get("status") or "") == "ok"
        )
        effects_ok = (
            isinstance(topic_source_lens_effects, dict)
            and str(topic_source_lens_effects.get("status") or "") == "ok"
        )
        if differentiation_ok or effects_ok:
            analyzed_topic_count += 1
        else:
            unavailable_topic_count += 1

        topic_rows.append(
            {
                "topic": topic_display.get(topic_key) or topic_key,
                "n_articles": len(topic_rows_data),
                "n_sources": len(source_counts_counter),
                "source_counts": source_counts,
                "source_differentiation": topic_source_differentiation,
                "source_lens_effects": topic_source_lens_effects,
            }
        )

    topic_rows.sort(key=lambda row: (-int(row.get("n_articles", 0)), str(row.get("topic", "")).lower()))
    base_payload["topics"] = topic_rows
    base_payload["summary"] = {
        "topic_count": len(topic_rows),
        "analyzed_topic_count": analyzed_topic_count,
        "unavailable_topic_count": unavailable_topic_count,
    }
    return base_payload


def _tag_slice_lens_summary(
    rows: list[dict[str, float]],
    preferred_lenses: list[str] | None = None,
) -> dict[str, Any]:
    discovered = {
        lens_name
        for row in rows
        for lens_name, value in row.items()
        if isinstance(lens_name, str) and isinstance(value, (int, float))
    }
    lens_names = _ordered_lenses(preferred_lenses or [], discovered)
    lens_rows: list[dict[str, Any]] = []
    for lens_name in lens_names:
        values = [float(row[lens_name]) for row in rows if isinstance(row.get(lens_name), (int, float))]
        if not values:
            continue
        lens_rows.append(
            {
                "lens": lens_name,
                "n": len(values),
                "mean_percent": sum(values) / len(values),
                "min_percent": min(values),
                "max_percent": max(values),
            }
        )
    lens_rows.sort(key=lambda row: (-float(row.get("mean_percent", 0.0)), str(row.get("lens", "")).lower()))
    return {"lenses": lens_rows, "lens_count": len(lens_rows)}


def _tag_slice_trends(
    rows: list[dict[str, float]],
    article_meta_rows: list[dict[str, Any]],
    preferred_lenses: list[str] | None = None,
) -> dict[str, Any]:
    if len(rows) != len(article_meta_rows):
        return {"daily_counts": [], "daily_lens_means": []}

    daily_counter: Counter[str] = Counter()
    daily_lens_values: dict[str, dict[str, list[float]]] = defaultdict(lambda: defaultdict(list))
    discovered: set[str] = set()
    for lens_row, meta in zip(rows, article_meta_rows):
        published = parse_datetime(meta.get("published_at") if isinstance(meta, dict) else None)
        if published is None:
            continue
        day = published.date().isoformat()
        daily_counter[day] += 1
        for lens_name, value in lens_row.items():
            if isinstance(lens_name, str) and isinstance(value, (int, float)):
                discovered.add(lens_name)
                daily_lens_values[day][lens_name].append(float(value))

    lens_names = _ordered_lenses(preferred_lenses or [], discovered)
    daily_counts = [{"date": day, "count": daily_counter[day]} for day in sorted(daily_counter.keys())]
    daily_lens_means: list[dict[str, Any]] = []
    for day in sorted(daily_lens_values.keys()):
        row: dict[str, Any] = {"date": day}
        for lens_name in lens_names:
            values = daily_lens_values[day].get(lens_name, [])
            if values:
                row[lens_name] = sum(values) / len(values)
        daily_lens_means.append(row)
    return {"daily_counts": daily_counts, "daily_lens_means": daily_lens_means}


def _tag_sliced_analysis_from_records(
    article_lens_percentages: list[dict[str, float]],
    source_labels: list[str],
    tag_keys_for_lens_rows: list[list[str]],
    tag_display_labels: dict[str, str],
    article_meta_rows: list[dict[str, Any]],
    pooled_source_differentiation: dict[str, Any],
    pooled_source_lens_effects: dict[str, Any],
    preferred_lenses: list[str] | None = None,
    top_n: int = 20,
) -> dict[str, Any]:
    base_payload: dict[str, Any] = {
        "tag_basis": "topic_tags",
        "multi_tag_policy": "duplicate_per_tag",
        "pooled_label": "tag-confounded",
        "top_n": top_n,
        "pooled": {
            "source_differentiation": (
                pooled_source_differentiation if isinstance(pooled_source_differentiation, dict) else {}
            ),
            "source_lens_effects": pooled_source_lens_effects if isinstance(pooled_source_lens_effects, dict) else {},
        },
        "tags": [],
        "summary": {
            "tag_count": 0,
            "shown_tag_count": 0,
            "analyzed_tag_count": 0,
            "unavailable_tag_count": 0,
            "total_memberships": 0,
        },
    }
    if (
        not article_lens_percentages
        or len(article_lens_percentages) != len(source_labels)
        or len(article_lens_percentages) != len(tag_keys_for_lens_rows)
        or len(article_lens_percentages) != len(article_meta_rows)
    ):
        return base_payload

    tag_display = dict(tag_display_labels)
    tag_display.setdefault("__untagged__", "Untagged")

    tag_buckets: dict[str, dict[str, Any]] = defaultdict(lambda: {"rows": [], "source_labels": [], "article_meta_rows": []})
    total_memberships = 0
    for lens_row, source_label, tag_keys, meta_row in zip(
        article_lens_percentages,
        source_labels,
        tag_keys_for_lens_rows,
        article_meta_rows,
    ):
        effective_keys: list[str] = []
        if isinstance(tag_keys, list):
            for tag_key in tag_keys:
                if not isinstance(tag_key, str):
                    continue
                normalized_key = tag_key.strip().lower()
                if normalized_key:
                    effective_keys.append(normalized_key)
        if not effective_keys:
            effective_keys = ["__untagged__"]

        unique_keys = list(dict.fromkeys(effective_keys))
        for tag_key in unique_keys:
            tag_buckets[tag_key]["rows"].append(lens_row)
            tag_buckets[tag_key]["source_labels"].append(source_label)
            tag_buckets[tag_key]["article_meta_rows"].append(meta_row)
            total_memberships += 1

    all_tag_keys = sorted(
        tag_buckets.keys(),
        key=lambda key: (-len(tag_buckets[key]["rows"]), str(tag_display.get(key) or key).lower()),
    )
    shown_keys = all_tag_keys[: max(top_n, 0)]
    if "__untagged__" in tag_buckets and "__untagged__" not in shown_keys:
        shown_keys.append("__untagged__")

    tag_rows: list[dict[str, Any]] = []
    analyzed_tag_count = 0
    unavailable_tag_count = 0
    for tag_key in shown_keys:
        bucket = tag_buckets[tag_key]
        tag_rows_data = bucket["rows"] if isinstance(bucket.get("rows"), list) else []
        tag_source_labels = bucket["source_labels"] if isinstance(bucket.get("source_labels"), list) else []
        tag_meta_rows = bucket["article_meta_rows"] if isinstance(bucket.get("article_meta_rows"), list) else []
        source_counts_counter: Counter[str] = Counter(tag_source_labels)
        source_counts = {
            source_name: count
            for source_name, count in sorted(
                source_counts_counter.items(),
                key=lambda item: (-item[1], item[0].lower()),
            )
        }

        tag_source_lens_effects = _source_lens_effects_from_records(
            tag_rows_data,
            tag_source_labels,
            preferred_lenses=preferred_lenses,
        )
        tag_source_differentiation = _source_differentiation_from_records(
            tag_rows_data,
            tag_source_labels,
            preferred_lenses=preferred_lenses,
        )

        differentiation_ok = (
            isinstance(tag_source_differentiation, dict)
            and str(tag_source_differentiation.get("status") or "") == "ok"
        )
        effects_ok = (
            isinstance(tag_source_lens_effects, dict)
            and str(tag_source_lens_effects.get("status") or "") == "ok"
        )
        if differentiation_ok or effects_ok:
            analyzed_tag_count += 1
        else:
            unavailable_tag_count += 1

        tag_rows.append(
            {
                "tag": tag_display.get(tag_key) or tag_key,
                "tag_key": tag_key,
                "n_articles": len(tag_rows_data),
                "n_sources": len(source_counts_counter),
                "source_counts": source_counts,
                "lens_summary": _tag_slice_lens_summary(tag_rows_data, preferred_lenses=preferred_lenses),
                "trends": _tag_slice_trends(tag_rows_data, tag_meta_rows, preferred_lenses=preferred_lenses),
                "source_differentiation": tag_source_differentiation,
                "source_lens_effects": tag_source_lens_effects,
            }
        )

    tag_rows.sort(key=lambda row: (-int(row.get("n_articles", 0)), str(row.get("tag", "")).lower()))
    base_payload["tags"] = tag_rows
    base_payload["summary"] = {
        "tag_count": len(all_tag_keys),
        "shown_tag_count": len(tag_rows),
        "analyzed_tag_count": analyzed_tag_count,
        "unavailable_tag_count": unavailable_tag_count,
        "total_memberships": total_memberships,
    }
    return base_payload


def _event_control_from_records(
    article_lens_percentages: list[dict[str, float]],
    source_labels: list[str],
    article_records: list[dict[str, Any]],
    preferred_lenses: list[str] | None = None,
) -> dict[str, Any]:
    event_control = build_event_clusters(
        article_records,
        source_labels,
        config=event_embedding_config_from_env(),
    )
    if str(event_control.get("status") or "") != "ok":
        return event_control

    event_member_indexes = event_control.pop("_event_member_indexes", [])
    event_control["event_coverage"] = _event_coverage_from_clusters(
        source_labels,
        event_control.get("events", []),
        event_member_indexes,
    )
    event_control["same_event_variance_decomposition"] = _same_event_variance_decomposition(
        article_lens_percentages,
        source_labels,
        event_control.get("events", []),
        event_member_indexes,
        preferred_lenses=preferred_lenses,
    )
    event_control["same_event_pairwise_source_lens_deltas"] = _same_event_pairwise_source_lens_deltas(
        article_lens_percentages,
        source_labels,
        event_control.get("events", []),
        event_member_indexes,
        preferred_lenses=preferred_lenses,
    )
    same_event_indexes: list[int] = []
    for event, member_indexes in zip(event_control.get("events", []), event_member_indexes):
        if not isinstance(event, dict) or not isinstance(member_indexes, list):
            continue
        source_counts = event.get("source_counts") if isinstance(event.get("source_counts"), dict) else {}
        if len(source_counts) < 2:
            continue
        for row_index in member_indexes:
            if isinstance(row_index, int):
                same_event_indexes.append(row_index)

    same_event_indexes = list(dict.fromkeys(same_event_indexes))
    same_event_rows = [
        article_lens_percentages[row_index]
        for row_index in same_event_indexes
        if 0 <= row_index < len(article_lens_percentages)
    ]
    same_event_sources = [
        source_labels[row_index]
        for row_index in same_event_indexes
        if 0 <= row_index < len(source_labels)
    ]

    if not same_event_rows or len(same_event_rows) != len(same_event_sources):
        reason = "No multi-source event clusters with scored article rows are available."
        event_control["same_event_source_differentiation"] = _source_differentiation_from_records(
            [],
            [],
            preferred_lenses=preferred_lenses,
        )
        event_control["same_event_source_differentiation"]["reason"] = reason
        event_control["same_event_source_lens_effects"] = _source_lens_effects_from_records(
            [],
            [],
            preferred_lenses=preferred_lenses,
        )
        event_control["same_event_source_lens_effects"]["reason"] = reason
        return event_control

    event_control["same_event_source_differentiation"] = _source_differentiation_from_records(
        same_event_rows,
        same_event_sources,
        preferred_lenses=preferred_lenses,
    )
    event_control["same_event_source_lens_effects"] = _source_lens_effects_from_records(
        same_event_rows,
        same_event_sources,
        preferred_lenses=preferred_lenses,
    )
    return event_control


def _same_event_pairwise_source_lens_deltas(
    article_lens_percentages: list[dict[str, float]],
    source_labels: list[str],
    events: list[Any],
    event_member_indexes: list[Any],
    preferred_lenses: list[str] | None = None,
) -> dict[str, Any]:
    method = "event_source_mean_pairwise_delta_v1"
    unavailable = {
        "status": "unavailable",
        "reason": "No multi-source event clusters with shared lens rows are available.",
        "method": method,
        "rows": [],
        "summary": {
            "source_pair_count": 0,
            "lens_count": 0,
            "row_count": 0,
            "event_pair_observation_count": 0,
        },
    }
    if not events or not event_member_indexes:
        return unavailable

    discovered_lenses = {
        lens_name
        for row in article_lens_percentages
        for lens_name, value in row.items()
        if isinstance(lens_name, str) and isinstance(value, (int, float))
    }
    if preferred_lenses:
        ordered_lenses = [lens_name for lens_name in preferred_lenses if lens_name in discovered_lenses]
        ordered_lenses.extend(sorted(discovered_lenses - set(ordered_lenses)))
    else:
        ordered_lenses = sorted(discovered_lenses)

    deltas_by_key: dict[tuple[str, str, str], list[dict[str, Any]]] = defaultdict(list)
    for event, member_indexes in zip(events, event_member_indexes):
        if not isinstance(event, dict) or not isinstance(member_indexes, list):
            continue
        event_id = str(event.get("event_id") or "")
        source_lens_values: dict[str, dict[str, list[float]]] = defaultdict(lambda: defaultdict(list))
        for row_index in member_indexes:
            if not isinstance(row_index, int) or row_index < 0 or row_index >= len(article_lens_percentages):
                continue
            if row_index >= len(source_labels):
                continue
            source_label = source_labels[row_index]
            lens_row = article_lens_percentages[row_index]
            for lens_name in ordered_lenses:
                value = lens_row.get(lens_name)
                if isinstance(value, (int, float)) and math.isfinite(float(value)):
                    source_lens_values[source_label][lens_name].append(float(value))

        source_means: dict[str, dict[str, float]] = {}
        for source_label, lens_values in source_lens_values.items():
            means = {
                lens_name: sum(values) / len(values)
                for lens_name, values in lens_values.items()
                if values
            }
            if means:
                source_means[source_label] = means

        sorted_sources = sorted(source_means.keys(), key=lambda value: value.lower())
        if len(sorted_sources) < 2:
            continue
        for left_idx, source_a in enumerate(sorted_sources):
            for source_b in sorted_sources[left_idx + 1 :]:
                means_a = source_means[source_a]
                means_b = source_means[source_b]
                for lens_name in ordered_lenses:
                    if lens_name not in means_a or lens_name not in means_b:
                        continue
                    delta = means_a[lens_name] - means_b[lens_name]
                    deltas_by_key[(source_a, source_b, lens_name)].append(
                        {
                            "event_id": event_id,
                            "delta": delta,
                            "source_a_mean": means_a[lens_name],
                            "source_b_mean": means_b[lens_name],
                        }
                    )

    rows: list[dict[str, Any]] = []
    source_pairs: set[tuple[str, str]] = set()
    lens_names: set[str] = set()
    event_pair_observation_count = 0
    for (source_a, source_b, lens_name), observations in deltas_by_key.items():
        deltas = [float(obs["delta"]) for obs in observations if isinstance(obs.get("delta"), (int, float))]
        if not deltas:
            continue
        source_pairs.add((source_a, source_b))
        lens_names.add(lens_name)
        event_pair_observation_count += len(deltas)
        event_ids = [str(obs.get("event_id") or "") for obs in observations if obs.get("event_id")]
        rows.append(
            {
                "source_a": source_a,
                "source_b": source_b,
                "lens": lens_name,
                "n_events": len(deltas),
                "mean_delta_a_minus_b": sum(deltas) / len(deltas),
                "median_delta_a_minus_b": statistics.median(deltas),
                "mean_abs_delta": sum(abs(delta) for delta in deltas) / len(deltas),
                "max_abs_delta": max(abs(delta) for delta in deltas),
                "source_a_higher_event_count": sum(1 for delta in deltas if delta > 0),
                "source_b_higher_event_count": sum(1 for delta in deltas if delta < 0),
                "tied_event_count": sum(1 for delta in deltas if delta == 0),
                "event_ids": event_ids,
            }
        )

    if not rows:
        return unavailable

    rows.sort(
        key=lambda row: (
            -float(row.get("mean_abs_delta") or 0.0),
            str(row.get("source_a", "")).lower(),
            str(row.get("source_b", "")).lower(),
            str(row.get("lens", "")).lower(),
        )
    )
    return {
        "status": "ok",
        "reason": "",
        "method": method,
        "rows": rows,
        "summary": {
            "source_pair_count": len(source_pairs),
            "lens_count": len(lens_names),
            "row_count": len(rows),
            "event_pair_observation_count": event_pair_observation_count,
        },
    }


def _event_coverage_from_clusters(
    source_labels: list[str],
    events: list[Any],
    event_member_indexes: list[Any],
) -> dict[str, Any]:
    method = "event_source_coverage_v1"
    unavailable = {
        "status": "unavailable",
        "reason": "No event clusters are available for source coverage diagnostics.",
        "method": method,
        "source_rows": [],
        "source_pair_rows": [],
        "summary": {
            "source_count": 0,
            "source_pair_count": 0,
            "event_article_memberships": 0,
            "multi_source_event_article_memberships": 0,
        },
    }
    if not events or not event_member_indexes:
        return unavailable

    total_source_articles = Counter(source_labels)
    source_event_ids: dict[str, set[str]] = defaultdict(set)
    source_multi_event_ids: dict[str, set[str]] = defaultdict(set)
    source_event_article_counts: Counter[str] = Counter()
    source_multi_event_article_counts: Counter[str] = Counter()
    pair_event_ids: dict[tuple[str, str], set[str]] = defaultdict(set)
    pair_article_counts: Counter[tuple[str, str]] = Counter()

    for event, member_indexes in zip(events, event_member_indexes):
        if not isinstance(event, dict) or not isinstance(member_indexes, list):
            continue
        event_id = str(event.get("event_id") or "")
        if not event_id:
            continue
        event_sources = []
        for row_index in member_indexes:
            if not isinstance(row_index, int) or row_index < 0 or row_index >= len(source_labels):
                continue
            source_label = source_labels[row_index]
            event_sources.append(source_label)
            source_event_ids[source_label].add(event_id)
            source_event_article_counts[source_label] += 1

        unique_sources = sorted(set(event_sources), key=lambda value: value.lower())
        if len(unique_sources) < 2:
            continue

        for source_label in event_sources:
            source_multi_event_ids[source_label].add(event_id)
            source_multi_event_article_counts[source_label] += 1

        event_source_counts = Counter(event_sources)
        for left_idx, source_a in enumerate(unique_sources):
            for source_b in unique_sources[left_idx + 1 :]:
                key = (source_a, source_b)
                pair_event_ids[key].add(event_id)
                pair_article_counts[key] += event_source_counts[source_a] + event_source_counts[source_b]

    source_names = sorted(set(total_source_articles) | set(source_event_ids), key=lambda value: value.lower())
    source_rows = []
    for source_name in source_names:
        total_articles = int(total_source_articles.get(source_name, 0))
        event_articles = int(source_event_article_counts.get(source_name, 0))
        multi_event_articles = int(source_multi_event_article_counts.get(source_name, 0))
        source_rows.append(
            {
                "source": source_name,
                "total_scored_articles": total_articles,
                "event_count": len(source_event_ids.get(source_name, set())),
                "multi_source_event_count": len(source_multi_event_ids.get(source_name, set())),
                "event_article_count": event_articles,
                "multi_source_event_article_count": multi_event_articles,
                "event_article_coverage_ratio": (event_articles / total_articles) if total_articles else 0.0,
                "multi_source_event_article_coverage_ratio": (multi_event_articles / total_articles) if total_articles else 0.0,
            }
        )

    source_rows.sort(
        key=lambda row: (
            -int(row.get("multi_source_event_count", 0)),
            -int(row.get("multi_source_event_article_count", 0)),
            str(row.get("source", "")).lower(),
        )
    )

    source_pair_rows = []
    for (source_a, source_b), event_ids in pair_event_ids.items():
        source_pair_rows.append(
            {
                "source_a": source_a,
                "source_b": source_b,
                "shared_event_count": len(event_ids),
                "shared_event_article_count": int(pair_article_counts.get((source_a, source_b), 0)),
                "event_ids": sorted(event_ids),
            }
        )
    source_pair_rows.sort(
        key=lambda row: (
            -int(row.get("shared_event_count", 0)),
            -int(row.get("shared_event_article_count", 0)),
            str(row.get("source_a", "")).lower(),
            str(row.get("source_b", "")).lower(),
        )
    )

    if not source_rows and not source_pair_rows:
        return unavailable

    return {
        "status": "ok",
        "reason": "",
        "method": method,
        "source_rows": source_rows,
        "source_pair_rows": source_pair_rows,
        "summary": {
            "source_count": len(source_rows),
            "source_pair_count": len(source_pair_rows),
            "event_article_memberships": sum(source_event_article_counts.values()),
            "multi_source_event_article_memberships": sum(source_multi_event_article_counts.values()),
        },
    }


def _same_event_variance_decomposition(
    article_lens_percentages: list[dict[str, float]],
    source_labels: list[str],
    events: list[Any],
    event_member_indexes: list[Any],
    preferred_lenses: list[str] | None = None,
) -> dict[str, Any]:
    method = "event_centered_source_variance_v1"
    unavailable = {
        "status": "unavailable",
        "reason": "No multi-source event clusters with shared lens rows are available.",
        "method": method,
        "rows": [],
        "summary": {"lens_count": 0, "row_count": 0, "event_count": 0, "source_count": 0},
    }
    if not events or not event_member_indexes:
        return unavailable

    observations: list[dict[str, Any]] = []
    for event, member_indexes in zip(events, event_member_indexes):
        if not isinstance(event, dict) or not isinstance(member_indexes, list):
            continue
        event_id = str(event.get("event_id") or "")
        source_counts = event.get("source_counts") if isinstance(event.get("source_counts"), dict) else {}
        if len(source_counts) < 2:
            continue
        for row_index in member_indexes:
            if not isinstance(row_index, int) or row_index < 0 or row_index >= len(article_lens_percentages):
                continue
            if row_index >= len(source_labels):
                continue
            observations.append(
                {
                    "event_id": event_id,
                    "source": source_labels[row_index],
                    "lens_row": article_lens_percentages[row_index],
                }
            )

    if not observations:
        return unavailable

    discovered_lenses = {
        lens_name
        for obs in observations
        for lens_name, value in obs["lens_row"].items()
        if isinstance(lens_name, str) and isinstance(value, (int, float)) and math.isfinite(float(value))
    }
    if preferred_lenses:
        lens_names = [lens_name for lens_name in preferred_lenses if lens_name in discovered_lenses]
        lens_names.extend(sorted(discovered_lenses - set(lens_names)))
    else:
        lens_names = sorted(discovered_lenses)

    rows: list[dict[str, Any]] = []
    for lens_name in lens_names:
        values: list[float] = []
        event_labels: list[str] = []
        source_labels_for_lens: list[str] = []
        for obs in observations:
            value = obs["lens_row"].get(lens_name)
            if not isinstance(value, (int, float)) or not math.isfinite(float(value)):
                continue
            values.append(float(value))
            event_labels.append(str(obs["event_id"]))
            source_labels_for_lens.append(str(obs["source"]))

        if len(values) < 2:
            continue
        unique_events = sorted(set(event_labels))
        unique_sources = sorted(set(source_labels_for_lens))
        if len(unique_events) < 1 or len(unique_sources) < 2:
            continue

        grand_mean = sum(values) / len(values)
        ss_total = sum((value - grand_mean) ** 2 for value in values)
        if ss_total <= 0:
            rows.append(
                {
                    "lens": lens_name,
                    "n": len(values),
                    "event_count": len(unique_events),
                    "source_count": len(unique_sources),
                    "overall_mean": grand_mean,
                    "ss_total": ss_total,
                    "event_eta_sq": 0.0,
                    "source_eta_sq_raw": 0.0,
                    "source_eta_sq_event_centered": 0.0,
                    "additive_event_source_r_squared": 0.0,
                    "residual_ss_additive": 0.0,
                    "strongest_source_after_event_control": None,
                    "source_residual_means": {},
                }
            )
            continue

        event_values: dict[str, list[float]] = defaultdict(list)
        source_values: dict[str, list[float]] = defaultdict(list)
        for value, event_id, source_label in zip(values, event_labels, source_labels_for_lens):
            event_values[event_id].append(value)
            source_values[source_label].append(value)

        event_means = {event_id: sum(vals) / len(vals) for event_id, vals in event_values.items() if vals}
        source_means = {source_label: sum(vals) / len(vals) for source_label, vals in source_values.items() if vals}
        ss_event = sum(len(event_values[event_id]) * ((event_means[event_id] - grand_mean) ** 2) for event_id in event_means)
        ss_source_raw = sum(
            len(source_values[source_label]) * ((source_means[source_label] - grand_mean) ** 2)
            for source_label in source_means
        )

        event_centered_values: list[float] = []
        event_centered_sources: list[str] = []
        for value, event_id, source_label in zip(values, event_labels, source_labels_for_lens):
            event_centered_values.append(value - event_means.get(event_id, grand_mean))
            event_centered_sources.append(source_label)
        centered_total_mean = sum(event_centered_values) / len(event_centered_values)
        centered_ss_total = sum((value - centered_total_mean) ** 2 for value in event_centered_values)
        centered_by_source: dict[str, list[float]] = defaultdict(list)
        for value, source_label in zip(event_centered_values, event_centered_sources):
            centered_by_source[source_label].append(value)
        source_residual_means = {
            source_label: sum(vals) / len(vals)
            for source_label, vals in centered_by_source.items()
            if vals
        }
        centered_ss_source = sum(
            len(centered_by_source[source_label]) * ((source_residual_means[source_label] - centered_total_mean) ** 2)
            for source_label in source_residual_means
        )

        additive_residual_ss = 0.0
        for value, event_id, source_label in zip(values, event_labels, source_labels_for_lens):
            predicted = event_means.get(event_id, grand_mean) + source_means.get(source_label, grand_mean) - grand_mean
            additive_residual_ss += (value - predicted) ** 2

        strongest_source = None
        if source_residual_means:
            strongest_source = max(source_residual_means.items(), key=lambda item: abs(item[1]))[0]

        rows.append(
            {
                "lens": lens_name,
                "n": len(values),
                "event_count": len(unique_events),
                "source_count": len(unique_sources),
                "overall_mean": grand_mean,
                "ss_total": ss_total,
                "event_eta_sq": ss_event / ss_total,
                "source_eta_sq_raw": ss_source_raw / ss_total,
                "source_eta_sq_event_centered": (centered_ss_source / centered_ss_total) if centered_ss_total > 0 else 0.0,
                "additive_event_source_r_squared": max(0.0, min(1.0, 1.0 - (additive_residual_ss / ss_total))),
                "residual_ss_additive": additive_residual_ss,
                "strongest_source_after_event_control": strongest_source,
                "source_residual_means": dict(
                    sorted(source_residual_means.items(), key=lambda item: (-abs(item[1]), item[0].lower()))
                ),
            }
        )

    if not rows:
        return unavailable

    rows.sort(
        key=lambda row: (
            -float(row.get("source_eta_sq_event_centered") or 0.0),
            -float(row.get("additive_event_source_r_squared") or 0.0),
            str(row.get("lens", "")).lower(),
        )
    )
    return {
        "status": "ok",
        "reason": "",
        "method": method,
        "rows": rows,
        "summary": {
            "lens_count": len(rows),
            "row_count": len(rows),
            "event_count": len({obs["event_id"] for obs in observations if obs.get("event_id")}),
            "source_count": len({obs["source"] for obs in observations if obs.get("source")}),
        },
    }


def _source_reliability_assessment(
    source_differentiation: dict[str, Any] | None,
    source_lens_effects: dict[str, Any] | None,
) -> dict[str, Any]:
    source_differentiation = source_differentiation if isinstance(source_differentiation, dict) else {}
    source_lens_effects = source_lens_effects if isinstance(source_lens_effects, dict) else {}

    differentiation_status = str(source_differentiation.get("status") or "unavailable")
    effects_status = str(source_lens_effects.get("status") or "unavailable")
    n_articles = int(source_differentiation.get("n_articles", 0) or 0)
    n_sources = int(source_differentiation.get("n_sources", 0) or 0)
    n_lenses = int(source_differentiation.get("n_lenses", 0) or 0)

    classification = (
        source_differentiation.get("classification")
        if isinstance(source_differentiation.get("classification"), dict)
        else {}
    )
    multivariate = (
        source_differentiation.get("multivariate")
        if isinstance(source_differentiation.get("multivariate"), dict)
        else {}
    )
    rows = source_lens_effects.get("rows") if isinstance(source_lens_effects.get("rows"), list) else []
    q_values = [float(row.get("p_perm_fdr")) for row in rows if isinstance(row, dict) and isinstance(row.get("p_perm_fdr"), (int, float))]
    significant_lens_count = sum(1 for q_value in q_values if q_value <= 0.05)
    best_q = min(q_values) if q_values else None
    total_lens_tests = len(q_values)

    classification_accuracy = _coerce_float(classification.get("accuracy"))
    classification_baseline = _coerce_float(classification.get("baseline_accuracy"))
    classification_lift = None
    if classification_accuracy is not None and classification_baseline is not None:
        classification_lift = classification_accuracy - classification_baseline

    classification_p = _coerce_float(classification.get("p_perm"))
    multivariate_p = _coerce_float(multivariate.get("p_perm"))

    flags: list[str] = []
    if n_articles < 20:
        flags.append("low_article_count")
    if n_sources < 2:
        flags.append("insufficient_source_count")
    if differentiation_status != "ok":
        flags.append("source_differentiation_unavailable")
    if effects_status != "ok":
        flags.append("source_lens_effects_unavailable")
    if significant_lens_count == 0 and effects_status == "ok":
        flags.append("no_fdr_significant_lens_effects")
    if isinstance(classification_lift, (int, float)) and float(classification_lift) <= 0:
        flags.append("no_classification_lift")

    if differentiation_status != "ok" and effects_status != "ok":
        return {
            "status": "unavailable",
            "tier": "unavailable",
            "score": None,
            "flags": list(dict.fromkeys(flags)),
            "metrics": {
                "n_articles": n_articles,
                "n_sources": n_sources,
                "n_lenses": n_lenses,
                "classification_accuracy": classification_accuracy,
                "classification_baseline_accuracy": classification_baseline,
                "classification_lift": classification_lift,
                "classification_p_perm": classification_p,
                "multivariate_p_perm": multivariate_p,
                "best_q_value": best_q,
                "fdr_significant_lens_count": significant_lens_count,
                "total_lens_tests": total_lens_tests,
            },
            "reason": "Source differentiation and lens effects are both unavailable for this slice.",
        }

    score = 0.0
    if n_articles >= 120:
        score += 0.25
    elif n_articles >= 60:
        score += 0.20
    elif n_articles >= 30:
        score += 0.15
    elif n_articles >= 15:
        score += 0.10
    elif n_articles >= 8:
        score += 0.05

    if n_sources >= 4:
        score += 0.15
    elif n_sources == 3:
        score += 0.10
    elif n_sources == 2:
        score += 0.05

    if isinstance(multivariate_p, (int, float)):
        if multivariate_p <= 0.05:
            score += 0.20
        elif multivariate_p <= 0.10:
            score += 0.10
    if isinstance(classification_p, (int, float)):
        if classification_p <= 0.05:
            score += 0.20
        elif classification_p <= 0.10:
            score += 0.10

    if isinstance(classification_lift, (int, float)):
        if classification_lift >= 0.15:
            score += 0.15
        elif classification_lift >= 0.08:
            score += 0.10
        elif classification_lift >= 0.03:
            score += 0.05

    if significant_lens_count >= 3:
        score += 0.15
    elif significant_lens_count >= 1:
        score += 0.10

    if isinstance(best_q, (int, float)):
        if best_q <= 0.01:
            score += 0.10
        elif best_q <= 0.05:
            score += 0.07
        elif best_q <= 0.10:
            score += 0.04

    if total_lens_tests >= 10:
        score += 0.05
    elif total_lens_tests >= 5:
        score += 0.03

    if n_articles < 12:
        score = min(score, 0.35)
    elif n_articles < 20:
        score = min(score, 0.50)
    if n_sources < 2:
        score = min(score, 0.25)

    score = min(max(score, 0.0), 1.0)
    if score >= 0.70:
        tier = "high"
    elif score >= 0.45:
        tier = "moderate"
    else:
        tier = "low"

    return {
        "status": "ok",
        "tier": tier,
        "score": score,
        "flags": list(dict.fromkeys(flags)),
        "metrics": {
            "n_articles": n_articles,
            "n_sources": n_sources,
            "n_lenses": n_lenses,
            "classification_accuracy": classification_accuracy,
            "classification_baseline_accuracy": classification_baseline,
            "classification_lift": classification_lift,
            "classification_p_perm": classification_p,
            "multivariate_p_perm": multivariate_p,
            "best_q_value": best_q,
            "fdr_significant_lens_count": significant_lens_count,
            "total_lens_tests": total_lens_tests,
        },
        "reason": "",
    }


def _source_reliability_from_topic_control(
    source_differentiation: dict[str, Any],
    source_lens_effects: dict[str, Any],
    source_topic_control: dict[str, Any],
    tag_sliced_analysis: dict[str, Any] | None = None,
    event_control: dict[str, Any] | None = None,
) -> dict[str, Any]:
    pooled_assessment = _source_reliability_assessment(source_differentiation, source_lens_effects)
    event_control = event_control if isinstance(event_control, dict) else {}
    event_controlled_assessment = _source_reliability_assessment(
        event_control.get("same_event_source_differentiation")
        if isinstance(event_control.get("same_event_source_differentiation"), dict)
        else {},
        event_control.get("same_event_source_lens_effects")
        if isinstance(event_control.get("same_event_source_lens_effects"), dict)
        else {},
    )

    topic_rows = source_topic_control.get("topics") if isinstance(source_topic_control.get("topics"), list) else []
    topic_assessments: list[dict[str, Any]] = []
    for topic_row in topic_rows:
        if not isinstance(topic_row, dict):
            continue
        topic_name = str(topic_row.get("topic") or "").strip()
        if not topic_name:
            continue
        topic_assessments.append(
            {
                "topic": topic_name,
                "assessment": _source_reliability_assessment(
                    topic_row.get("source_differentiation") if isinstance(topic_row.get("source_differentiation"), dict) else {},
                    topic_row.get("source_lens_effects") if isinstance(topic_row.get("source_lens_effects"), dict) else {},
                ),
            }
        )

    tag_sliced_analysis = tag_sliced_analysis if isinstance(tag_sliced_analysis, dict) else {}
    tag_rows = tag_sliced_analysis.get("tags") if isinstance(tag_sliced_analysis.get("tags"), list) else []
    tag_assessments: list[dict[str, Any]] = []
    for tag_row in tag_rows:
        if not isinstance(tag_row, dict):
            continue
        tag_name = str(tag_row.get("tag") or "").strip()
        if not tag_name:
            continue
        tag_assessments.append(
            {
                "tag": tag_name,
                "assessment": _source_reliability_assessment(
                    tag_row.get("source_differentiation") if isinstance(tag_row.get("source_differentiation"), dict) else {},
                    tag_row.get("source_lens_effects") if isinstance(tag_row.get("source_lens_effects"), dict) else {},
                ),
            }
        )

    topic_tier_counter: Counter[str] = Counter()
    topic_status_counter: Counter[str] = Counter()
    for topic_item in topic_assessments:
        assessment = topic_item.get("assessment") if isinstance(topic_item.get("assessment"), dict) else {}
        topic_tier_counter[str(assessment.get("tier") or "unavailable")] += 1
        topic_status_counter[str(assessment.get("status") or "unavailable")] += 1

    tag_tier_counter: Counter[str] = Counter()
    tag_status_counter: Counter[str] = Counter()
    for tag_item in tag_assessments:
        assessment = tag_item.get("assessment") if isinstance(tag_item.get("assessment"), dict) else {}
        tag_tier_counter[str(assessment.get("tier") or "unavailable")] += 1
        tag_status_counter[str(assessment.get("status") or "unavailable")] += 1

    return {
        "method": "heuristic-v1",
        "pooled_label": "topic-confounded",
        "tag_basis": tag_sliced_analysis.get("tag_basis") or "topic_tags",
        "pooled": pooled_assessment,
        "event_controlled": event_controlled_assessment,
        "topics": topic_assessments,
        "tags": tag_assessments,
        "summary": {
            "topic_count": len(topic_assessments),
            "ok_topic_count": topic_status_counter.get("ok", 0),
            "unavailable_topic_count": topic_status_counter.get("unavailable", 0),
            "high_count": topic_tier_counter.get("high", 0),
            "moderate_count": topic_tier_counter.get("moderate", 0),
            "low_count": topic_tier_counter.get("low", 0),
            "unavailable_count": topic_tier_counter.get("unavailable", 0),
            "tag_count": len(tag_assessments),
            "ok_tag_count": tag_status_counter.get("ok", 0),
            "unavailable_tag_count": tag_status_counter.get("unavailable", 0),
            "high_tag_count": tag_tier_counter.get("high", 0),
            "moderate_tag_count": tag_tier_counter.get("moderate", 0),
            "low_tag_count": tag_tier_counter.get("low", 0),
            "unavailable_tag_reliability_count": tag_tier_counter.get("unavailable", 0),
            "event_controlled_status": event_controlled_assessment.get("status") or "unavailable",
            "event_controlled_tier": event_controlled_assessment.get("tier") or "unavailable",
        },
    }


def derive_stats(records: list[dict[str, Any]], payload: Any) -> dict[str, Any]:
    input_records = extract_records(payload)
    excluded_unscraped_articles = len(input_records) - len(records)
    summary = payload.get("summary") if isinstance(payload, dict) else None
    analysis = payload.get("analysis") if isinstance(payload, dict) else None
    lens_maxima = _lens_max_map_from_analysis(analysis)

    source_counter: Counter[str] = Counter()
    tag_counter: Counter[str] = Counter()
    daily_counter: Counter[str] = Counter()
    publish_hour_counter: Counter[int] = Counter()
    tag_count_distribution_counter: Counter[str] = Counter()
    source_tag_counter: Counter[tuple[str, str]] = Counter()
    scored_source_counter: Counter[str] = Counter()
    unscorable_source_counter: Counter[str] = Counter()
    zero_score_source_counter: Counter[str] = Counter()
    placeholder_zero_source_counter: Counter[str] = Counter()
    article_lens_percentages: list[dict[str, float]] = []
    source_labels_for_lens_rows: list[str] = []
    topic_keys_for_lens_rows: list[list[str]] = []
    topic_display_labels: dict[str, str] = {}
    article_meta_for_lens_rows: list[dict[str, Any]] = []
    article_records_for_lens_rows: list[dict[str, Any]] = []

    scored_articles = 0
    zero_score_articles = 0
    positive_score_articles = 0
    unscorable_articles = 0
    score_object_present_articles = 0
    score_object_missing_articles = 0
    placeholder_zero_unscorable_articles = 0

    for record in records:
        source_label = _source_label_for_record(record)
        source_counter[source_label] += 1

        unique_tags = {tag.strip() for tag in _tag_values_for_record(record) if tag.strip()}
        for tag in unique_tags:
            tag_counter[tag] += 1
            source_tag_counter[(source_label, tag)] += 1

        tag_count = len(unique_tags)
        tag_count_distribution_counter[_tag_count_distribution_label(tag_count)] += 1

        published_dt = _record_datetime(record)
        if published_dt is not None:
            daily_counter[published_dt.date().isoformat()] += 1
            publish_hour_counter[published_dt.hour] += 1

        score_details = _score_details_for_record(record)
        if score_details["has_score_object"]:
            score_object_present_articles += 1
        else:
            score_object_missing_articles += 1

        if score_details["status"] == "scored":
            scored_articles += 1
            scored_source_counter[source_label] += 1
            if score_details["is_zero_percent"]:
                zero_score_articles += 1
                zero_score_source_counter[source_label] += 1
            elif score_details["is_positive_percent"]:
                positive_score_articles += 1
        else:
            unscorable_articles += 1
            unscorable_source_counter[source_label] += 1
            if score_details["likely_placeholder_zero"]:
                placeholder_zero_unscorable_articles += 1
                placeholder_zero_source_counter[source_label] += 1

        lens_percentages = _record_lens_percentages(record, lens_maxima)
        if lens_percentages:
            topic_keys = _topic_memberships_from_record(record, topic_display_labels)
            strongest_lens, strongest_percent = max(lens_percentages.items(), key=lambda item: item[1])
            article_lens_percentages.append(lens_percentages)
            source_labels_for_lens_rows.append(source_label)
            topic_keys_for_lens_rows.append(topic_keys)
            article_records_for_lens_rows.append(record)
            article_meta_for_lens_rows.append(
                {
                    "id": _clean_text(record.get("id")),
                    "title": _clean_text(record.get("title")),
                    "source": source_label,
                    "published_at": _clean_text(record.get("published_at")),
                    "strongest_lens": strongest_lens,
                    "strongest_percent": strongest_percent,
                }
            )

    source_counts = [{"source": source, "count": count} for source, count in source_counter.most_common()]
    tag_counts = [{"tag": tag, "count": count} for tag, count in tag_counter.most_common()]
    daily_counts = [{"date": day, "count": daily_counter[day]} for day in sorted(daily_counter.keys())]
    publish_hour_counts = [{"hour": hour, "count": publish_hour_counter.get(hour, 0)} for hour in range(24)]

    tag_count_distribution = []
    for label in _TAG_COUNT_DISTRIBUTION_LABELS:
        if label == "5+":
            min_value, max_value = 5, None
        else:
            value = int(label)
            min_value, max_value = value, value
        tag_count_distribution.append(
            {
                "label": label,
                "min": min_value,
                "max": max_value,
                "count": tag_count_distribution_counter.get(label, 0),
            }
        )

    source_tag_matrix = [
        {"source": source_name, "tag": tag_name, "count": count}
        for (source_name, tag_name), count in sorted(
            source_tag_counter.items(),
            key=lambda item: (-item[1], item[0][0].lower(), item[0][1].lower()),
        )
    ]
    source_tag_totals_counter: Counter[str] = Counter()
    tag_totals_counter: Counter[str] = Counter()
    for (source_name, tag_name), count in source_tag_counter.items():
        source_tag_totals_counter[source_name] += count
        tag_totals_counter[tag_name] += count
    source_tag_totals = [{"source": source_name, "count": count} for source_name, count in source_tag_totals_counter.most_common()]
    tag_totals = [{"tag": tag_name, "count": count} for tag_name, count in tag_totals_counter.most_common()]

    scored_by_source = [
        {"source": source_name, "count": count}
        for source_name, count in scored_source_counter.most_common()
    ]
    score_status_by_source: list[dict[str, Any]] = []
    for source_name, source_count in source_counter.most_common():
        score_status_by_source.append(
            {
                "source": source_name,
                "total": source_count,
                "scored": scored_source_counter.get(source_name, 0),
                "zero_score": zero_score_source_counter.get(source_name, 0),
                "unscorable": unscorable_source_counter.get(source_name, 0),
                "placeholder_zero_unscorable": placeholder_zero_source_counter.get(source_name, 0),
            }
        )

    lens_correlations = _lens_correlations_from_records(
        article_lens_percentages,
        preferred_lenses=list(lens_maxima.keys()),
    )
    lens_pca = _lens_pca_from_records(
        article_lens_percentages,
        source_labels_for_lens_rows,
        article_meta_rows=article_meta_for_lens_rows,
        preferred_lenses=list(lens_maxima.keys()),
    )
    lens_mds = _lens_mds_from_records(
        article_lens_percentages,
        source_labels_for_lens_rows,
        article_meta_rows=article_meta_for_lens_rows,
        preferred_lenses=list(lens_maxima.keys()),
    )
    lens_separation = _lens_separation_from_records(
        article_lens_percentages,
        source_labels_for_lens_rows,
        preferred_lenses=list(lens_maxima.keys()),
    )
    latent_space_stability = _latent_space_stability_from_records(
        article_lens_percentages,
        source_labels_for_lens_rows,
        article_meta_for_lens_rows,
        lens_pca,
        preferred_lenses=list(lens_maxima.keys()),
    )
    lens_time_series = _lens_time_series_from_records(records, lens_maxima)
    lens_temporal_embedding = _lens_temporal_embedding_from_pca(lens_pca)
    lens_temporal_embedding_mds = _lens_temporal_embedding_from_mds(lens_mds)
    drift_diagnostics = _drift_diagnostics_from_records(records, lens_maxima)
    source_lens_effects = _source_lens_effects_from_records(
        article_lens_percentages,
        source_labels_for_lens_rows,
        preferred_lenses=list(lens_maxima.keys()),
    )
    source_differentiation = _source_differentiation_from_records(
        article_lens_percentages,
        source_labels_for_lens_rows,
        preferred_lenses=list(lens_maxima.keys()),
    )
    source_topic_control = _source_topic_control_from_records(
        article_lens_percentages,
        source_labels_for_lens_rows,
        topic_keys_for_lens_rows,
        topic_display_labels,
        pooled_source_differentiation=source_differentiation,
        pooled_source_lens_effects=source_lens_effects,
        preferred_lenses=list(lens_maxima.keys()),
    )
    tag_sliced_analysis = _tag_sliced_analysis_from_records(
        article_lens_percentages,
        source_labels_for_lens_rows,
        topic_keys_for_lens_rows,
        topic_display_labels,
        article_meta_for_lens_rows,
        pooled_source_differentiation=source_differentiation,
        pooled_source_lens_effects=source_lens_effects,
        preferred_lenses=list(lens_maxima.keys()),
    )
    event_control = _event_control_from_records(
        article_lens_percentages,
        source_labels_for_lens_rows,
        article_records_for_lens_rows,
        preferred_lenses=list(lens_maxima.keys()),
    )
    source_reliability = _source_reliability_from_topic_control(
        source_differentiation,
        source_lens_effects,
        source_topic_control,
        tag_sliced_analysis,
        event_control,
    )
    lens_views = _lens_views_from_records(records, lens_maxima)
    data_quality = _data_quality_from_records(records)
    lens_inventory = _lens_inventory_from_records(
        records,
        analysis if isinstance(analysis, dict) else None,
        lens_maxima,
    )
    source_tag_views = _source_tag_views_from_aggregates(
        source_tag_counter,
        source_tag_matrix,
        source_tag_totals,
        tag_totals,
    )

    total_articles = len(records)
    score_coverage_ratio = (scored_articles / total_articles) if total_articles else 0.0

    return {
        "input_articles": len(input_records),
        "excluded_unscraped_articles": excluded_unscraped_articles,
        "total_articles": total_articles,
        "scored_articles": scored_articles,
        "zero_score_articles": zero_score_articles,
        "positive_score_articles": positive_score_articles,
        "unscorable_articles": unscorable_articles,
        "score_object_present_articles": score_object_present_articles,
        "score_object_missing_articles": score_object_missing_articles,
        "placeholder_zero_unscorable_articles": placeholder_zero_unscorable_articles,
        "score_status": {
            "scored": scored_articles,
            "positive": positive_score_articles,
            "zero": zero_score_articles,
            "unscorable": unscorable_articles,
            "score_object_present": score_object_present_articles,
            "score_object_missing": score_object_missing_articles,
            "placeholder_zero_unscorable": placeholder_zero_unscorable_articles,
        },
        "score_coverage_ratio": score_coverage_ratio,
        "source_counts": source_counts,
        "tag_counts": tag_counts,
        "lens_correlations": lens_correlations,
        "lens_pca": lens_pca,
        "lens_mds": lens_mds,
        "lens_separation": lens_separation,
        "latent_space_stability": latent_space_stability,
        "lens_time_series": lens_time_series,
        "lens_temporal_embedding": lens_temporal_embedding,
        "lens_temporal_embedding_mds": lens_temporal_embedding_mds,
        "drift_diagnostics": drift_diagnostics,
        "source_lens_effects": source_lens_effects,
        "source_differentiation": source_differentiation,
        "source_topic_control": source_topic_control,
        "tag_sliced_analysis": tag_sliced_analysis,
        "event_control": event_control,
        "source_reliability": source_reliability,
        "lens_views": lens_views,
        "source_tag_views": source_tag_views,
        "data_quality": data_quality,
        "lens_inventory": lens_inventory,
        "daily_counts_utc": daily_counts,
        "chart_aggregates": {
            "tag_count_distribution": tag_count_distribution,
            "publish_hour_counts_utc": publish_hour_counts,
            "source_tag_matrix": source_tag_matrix,
            "source_tag_totals": source_tag_totals,
            "tag_totals": tag_totals,
            "scored_by_source": scored_by_source,
            "score_status_by_source": score_status_by_source,
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
        self.current_source_url = (
            _clean_config_url(source_url)
            or _clean_config_url(os.getenv("RSS_DAILY_JSON_URL"))
            or DEFAULT_RSS_DAILY_JSON_URL
        )
        self.source_url = self.current_source_url
        self.history_url_template = (
            _clean_config_url(os.getenv("RSS_HISTORY_JSON_URL_TEMPLATE"))
            or DEFAULT_RSS_HISTORY_JSON_URL_TEMPLATE
        )
        self.current_ttl_seconds = _coerce_int(
            ttl_seconds if ttl_seconds is not None else os.getenv("RSS_CACHE_TTL_SECONDS"),
            default=3600,
        )
        self.snapshot_ttl_seconds = _coerce_int(
            os.getenv("RSS_SNAPSHOT_CACHE_TTL_SECONDS"),
            default=self.current_ttl_seconds,
        )
        self.snapshot_cache_max_entries = _coerce_int(
            os.getenv("RSS_SNAPSHOT_CACHE_MAX_ENTRIES"),
            default=30,
        )
        # Backward-compatible alias used by some callers/tests for current-mode TTL.
        self.ttl_seconds = self.current_ttl_seconds
        self.timeout_seconds = _coerce_int(
            timeout_seconds if timeout_seconds is not None else os.getenv("RSS_HTTP_TIMEOUT_SECONDS"),
            default=20,
        )
        self.max_age_seconds = _coerce_int(os.getenv("RSS_MAX_AGE_SECONDS"), default=36 * 3600)

        self._lock = threading.Lock()
        self._cache_states: dict[str, dict[str, Any]] = {}
        self._snapshot_lru: OrderedDict[str, None] = OrderedDict()

    def _empty_cache_state(self) -> dict[str, Any]:
        return {
            "bundle": None,
            "fetched_at": None,
            "cache_until_epoch": 0.0,
            "is_last_good": False,
            "last_fetch_error": None,
            "last_good_bundle": None,
            "last_good_fetched_at": None,
            "etag": None,
        }

    def _cache_key(self, snapshot_date: str | None) -> str:
        if snapshot_date:
            return f"snapshot:{snapshot_date}"
        return "current"

    def _cache_ttl_seconds(self, source_mode: str) -> int:
        if source_mode == "snapshot":
            return self.snapshot_ttl_seconds
        return self.current_ttl_seconds

    def _touch_snapshot_cache_key(self, cache_key: str) -> None:
        self._snapshot_lru.pop(cache_key, None)
        self._snapshot_lru[cache_key] = None

    def _evict_snapshot_cache_if_needed(self, keep_key: str | None = None) -> None:
        while len(self._snapshot_lru) > self.snapshot_cache_max_entries:
            evict_key = next(iter(self._snapshot_lru))
            if keep_key is not None and evict_key == keep_key:
                self._snapshot_lru.move_to_end(evict_key)
                continue
            self._snapshot_lru.pop(evict_key, None)
            self._cache_states.pop(evict_key, None)

    def _resolve_source_url(self, snapshot_date: str | None) -> str:
        if snapshot_date:
            if "{date}" not in self.history_url_template:
                raise RuntimeError("RSS_HISTORY_JSON_URL_TEMPLATE must include {date}")
            return self.history_url_template.format(date=snapshot_date)
        return self.current_source_url

    def _fetch_json(self, source_url: str, etag: str | None) -> tuple[Any | None, str | None, bool]:
        if not source_url:
            raise RuntimeError("RSS source URL is not set")

        headers = {
            "Accept": "application/json",
            "User-Agent": "ml-sentiment-rss-consumer/1.0",
        }
        if etag:
            headers["If-None-Match"] = etag

        request = Request(
            source_url,
            headers=headers,
        )
        try:
            with urlopen(request, timeout=self.timeout_seconds) as response:
                content = response.read().decode("utf-8")
                response_etag = response.headers.get("ETag")
            return json.loads(content), response_etag, False
        except HTTPError as exc:
            if exc.code == 304:
                return None, etag, True
            if exc.code == 404:
                raise RssDigestNotFoundError(f"Upstream JSON not found at {source_url}") from exc
            raise RssDigestUpstreamError(
                f"HTTP {exc.code} while fetching upstream JSON from {source_url}"
            ) from exc
        except FileNotFoundError as exc:
            raise RssDigestNotFoundError(f"Upstream JSON not found at {source_url}") from exc
        except URLError as exc:
            reason = getattr(exc, "reason", exc)
            if isinstance(reason, FileNotFoundError):
                raise RssDigestNotFoundError(f"Upstream JSON not found at {source_url}") from exc
            if isinstance(reason, OSError) and getattr(reason, "errno", None) == 2:
                raise RssDigestNotFoundError(f"Upstream JSON not found at {source_url}") from exc
            raise RssDigestUpstreamError(
                f"Network error while fetching upstream JSON from {source_url}: {reason}"
            ) from exc

    def _build_bundle_from_payload(self, payload: Any) -> dict[str, Any]:
        generated_at = extract_generated_at(payload)
        digest = payload.get("digest") if isinstance(payload, dict) else None
        digest_obj = digest if isinstance(digest, dict) else {}
        digest_generated_at = parse_datetime(digest_obj.get("generated_at"))

        input_records = extract_records(payload)
        records = normalize_articles(payload)
        ordered_records = sort_records_desc(records)
        stats = derive_stats(ordered_records, payload)
        excluded_unscraped_articles = len(input_records) - len(ordered_records)

        return {
            "upstream_payload": payload,
            "articles_normalized": ordered_records,
            "stats": stats,
            "input_articles_count": len(input_records),
            "excluded_unscraped_articles": excluded_unscraped_articles,
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
        source_url: str,
        source_mode: str,
        snapshot_date: str | None,
        from_cache: bool,
        using_last_good: bool,
        error: str | None,
        etag: str | None,
        ttl_seconds: int,
    ) -> dict[str, Any]:
        return {
            **bundle,
            "fetched_at": _as_iso_utc(fetched_at),
            "source_url": source_url,
            "source_mode": source_mode,
            "snapshot_date": snapshot_date,
            "ttl_seconds": ttl_seconds,
            "from_cache": from_cache,
            "using_last_good": using_last_good,
            "error": error,
            "etag": etag,
        }

    def get_payload(self, force_refresh: bool = False, snapshot_date: str | None = None) -> dict[str, Any]:
        snapshot_date_value = parse_snapshot_date(snapshot_date)
        source_mode = "snapshot" if snapshot_date_value else "current"
        source_url = self._resolve_source_url(snapshot_date_value)
        cache_key = self._cache_key(snapshot_date_value)
        cache_ttl_seconds = self._cache_ttl_seconds(source_mode)
        now_epoch = time.time()
        with self._lock:
            cache_state = self._cache_states.setdefault(cache_key, self._empty_cache_state())
            if source_mode == "snapshot":
                self._touch_snapshot_cache_key(cache_key)
                self._evict_snapshot_cache_if_needed(keep_key=cache_key)
            cache_valid = cache_state["bundle"] is not None and now_epoch < cache_state["cache_until_epoch"]
            if cache_valid and not force_refresh:
                return self._format_bundle(
                    bundle=cache_state["bundle"],
                    fetched_at=cache_state["fetched_at"],
                    source_url=source_url,
                    source_mode=source_mode,
                    snapshot_date=snapshot_date_value,
                    from_cache=True,
                    using_last_good=bool(cache_state["is_last_good"]),
                    error=cache_state["last_fetch_error"],
                    etag=cache_state["etag"],
                    ttl_seconds=cache_ttl_seconds,
                )

            try:
                payload, etag, not_modified = self._fetch_json(source_url=source_url, etag=cache_state["etag"])
                fetched_at = datetime.now(timezone.utc)
                if etag:
                    cache_state["etag"] = etag

                if not_modified:
                    if cache_state["bundle"] is not None:
                        bundle = cache_state["bundle"]
                    elif source_mode == "current" and cache_state["last_good_bundle"] is not None:
                        bundle = cache_state["last_good_bundle"]
                    else:
                        raise RssDigestUpstreamError("Received 304 but no cached payload is available")
                else:
                    bundle = self._build_bundle_from_payload(payload)

                cache_state["bundle"] = bundle
                cache_state["fetched_at"] = fetched_at
                cache_state["cache_until_epoch"] = now_epoch + cache_ttl_seconds
                cache_state["is_last_good"] = False
                cache_state["last_fetch_error"] = None
                if source_mode == "current":
                    cache_state["last_good_bundle"] = bundle
                    cache_state["last_good_fetched_at"] = fetched_at

                return self._format_bundle(
                    bundle=bundle,
                    fetched_at=fetched_at,
                    source_url=source_url,
                    source_mode=source_mode,
                    snapshot_date=snapshot_date_value,
                    from_cache=False,
                    using_last_good=False,
                    error=None,
                    etag=cache_state["etag"],
                    ttl_seconds=cache_ttl_seconds,
                )
            except Exception as exc:  # noqa: BLE001
                if source_mode != "current":
                    raise

                if cache_state["last_good_bundle"] is None:
                    raise

                cache_state["last_fetch_error"] = f"{type(exc).__name__}: {exc}"
                cache_state["bundle"] = cache_state["last_good_bundle"]
                cache_state["fetched_at"] = cache_state["last_good_fetched_at"]
                cache_state["cache_until_epoch"] = now_epoch + cache_ttl_seconds
                cache_state["is_last_good"] = True

                return self._format_bundle(
                    bundle=cache_state["last_good_bundle"],
                    fetched_at=cache_state["last_good_fetched_at"],
                    source_url=source_url,
                    source_mode=source_mode,
                    snapshot_date=snapshot_date_value,
                    from_cache=False,
                    using_last_good=True,
                    error=cache_state["last_fetch_error"],
                    etag=cache_state["etag"],
                    ttl_seconds=cache_ttl_seconds,
                )
