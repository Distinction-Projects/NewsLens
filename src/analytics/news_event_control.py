from __future__ import annotations

import hashlib
import json
import math
import os
import re
import sqlite3
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Protocol


DEFAULT_EVENT_EMBEDDING_MODEL = "text-embedding-3-small"
DEFAULT_EVENT_EMBEDDING_DIMENSIONS = 512
DEFAULT_EVENT_SIMILARITY_THRESHOLD = 0.86
DEFAULT_EVENT_DATE_WINDOW_DAYS = 3
DEFAULT_EVENT_EMBEDDING_CACHE_PATH = "data/cache/news_event_embeddings.sqlite"
DEFAULT_EVENT_EMBEDDING_BATCH_SIZE = 128
_BODY_SNIPPET_CHARS = 1200


class EmbeddingProvider(Protocol):
    def embed_texts(self, texts: list[str], *, model: str, dimensions: int) -> list[list[float]]:
        ...


@dataclass(frozen=True)
class EventEmbeddingConfig:
    enabled: bool
    model: str
    dimensions: int
    threshold: float
    date_window_days: int
    cache_path: Path
    batch_size: int


def _bool_env(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() not in {"0", "false", "no", "off"}


def _int_env(name: str, default: int, minimum: int = 1) -> int:
    raw = os.getenv(name)
    if raw is None:
        return default
    try:
        value = int(raw)
    except ValueError:
        return default
    return max(value, minimum)


def _float_env(name: str, default: float, minimum: float = 0.0, maximum: float = 1.0) -> float:
    raw = os.getenv(name)
    if raw is None:
        return default
    try:
        value = float(raw)
    except ValueError:
        return default
    return min(max(value, minimum), maximum)


def event_embedding_config_from_env() -> EventEmbeddingConfig:
    return EventEmbeddingConfig(
        enabled=_bool_env("NEWS_EVENT_EMBEDDINGS_ENABLED", True),
        model=(os.getenv("NEWS_EVENT_EMBEDDING_MODEL") or DEFAULT_EVENT_EMBEDDING_MODEL).strip()
        or DEFAULT_EVENT_EMBEDDING_MODEL,
        dimensions=_int_env("NEWS_EVENT_EMBEDDING_DIMENSIONS", DEFAULT_EVENT_EMBEDDING_DIMENSIONS),
        threshold=_float_env("NEWS_EVENT_SIMILARITY_THRESHOLD", DEFAULT_EVENT_SIMILARITY_THRESHOLD),
        date_window_days=_int_env("NEWS_EVENT_DATE_WINDOW_DAYS", DEFAULT_EVENT_DATE_WINDOW_DAYS),
        cache_path=Path(os.getenv("NEWS_EVENT_EMBEDDING_CACHE_PATH") or DEFAULT_EVENT_EMBEDDING_CACHE_PATH),
        batch_size=_int_env("NEWS_EVENT_EMBEDDING_BATCH_SIZE", DEFAULT_EVENT_EMBEDDING_BATCH_SIZE),
    )


def _clean_text(value: Any) -> str:
    text = str(value or "").strip()
    text = re.sub(r"\s+", " ", text)
    return text


def _text_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _parse_datetime(value: Any) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        parsed = value
    else:
        try:
            parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        except ValueError:
            return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def event_text_for_record(record: dict[str, Any]) -> str:
    parts = [
        _clean_text(record.get("title")),
        _clean_text(record.get("ai_summary")),
        _clean_text(record.get("summary")),
    ]
    if not any(parts):
        scraped = record.get("scraped") if isinstance(record.get("scraped"), dict) else {}
        parts.append(_clean_text(scraped.get("body_text"))[:_BODY_SNIPPET_CHARS])
    return " ".join(part for part in parts if part)


class SQLiteEmbeddingCache:
    def __init__(self, path: Path) -> None:
        self.path = path

    def _connect(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(str(self.path))
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS event_embeddings (
                text_hash TEXT NOT NULL,
                model TEXT NOT NULL,
                dimensions INTEGER NOT NULL,
                embedding_json TEXT NOT NULL,
                text_preview TEXT,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (text_hash, model, dimensions)
            );
            """
        )
        return conn

    def get_many(self, text_hashes: list[str], *, model: str, dimensions: int) -> dict[str, list[float]]:
        if not text_hashes:
            return {}
        found: dict[str, list[float]] = {}
        with self._connect() as conn:
            for start in range(0, len(text_hashes), 500):
                batch = text_hashes[start : start + 500]
                placeholders = ",".join("?" for _ in batch)
                rows = conn.execute(
                    f"""
                    SELECT text_hash, embedding_json
                    FROM event_embeddings
                    WHERE model = ? AND dimensions = ? AND text_hash IN ({placeholders});
                    """,
                    (model, dimensions, *batch),
                ).fetchall()
                for text_hash, embedding_json in rows:
                    try:
                        embedding = json.loads(embedding_json)
                    except json.JSONDecodeError:
                        continue
                    if isinstance(embedding, list):
                        found[text_hash] = [float(value) for value in embedding]
        return found

    def set_many(
        self,
        rows: list[tuple[str, str, list[float]]],
        *,
        model: str,
        dimensions: int,
    ) -> None:
        if not rows:
            return
        with self._connect() as conn:
            conn.executemany(
                """
                INSERT INTO event_embeddings (text_hash, model, dimensions, embedding_json, text_preview)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(text_hash, model, dimensions) DO UPDATE
                SET embedding_json = excluded.embedding_json,
                    text_preview = excluded.text_preview,
                    created_at = CURRENT_TIMESTAMP;
                """,
                [
                    (
                        text_hash,
                        model,
                        dimensions,
                        json.dumps(embedding, separators=(",", ":")),
                        text[:240],
                    )
                    for text_hash, text, embedding in rows
                ],
            )


class OpenAIEmbeddingProvider:
    def __init__(self, api_key: str | None = None) -> None:
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")

    def embed_texts(self, texts: list[str], *, model: str, dimensions: int) -> list[list[float]]:
        if not self.api_key:
            raise RuntimeError("OPENAI_API_KEY is not configured.")
        try:
            from openai import OpenAI
        except ImportError as exc:  # pragma: no cover - depends on optional package install
            raise RuntimeError("openai package is not installed.") from exc

        client = OpenAI(api_key=self.api_key)
        response = client.embeddings.create(model=model, input=texts, dimensions=dimensions)
        sorted_items = sorted(response.data, key=lambda item: item.index)
        return [[float(value) for value in item.embedding] for item in sorted_items]


def _cosine_similarity(left: list[float], right: list[float]) -> float | None:
    if not left or not right or len(left) != len(right):
        return None
    dot = 0.0
    left_norm = 0.0
    right_norm = 0.0
    for left_value, right_value in zip(left, right):
        dot += left_value * right_value
        left_norm += left_value * left_value
        right_norm += right_value * right_value
    if left_norm <= 0.0 or right_norm <= 0.0:
        return None
    return dot / (math.sqrt(left_norm) * math.sqrt(right_norm))


class _UnionFind:
    def __init__(self, size: int) -> None:
        self.parent = list(range(size))

    def find(self, value: int) -> int:
        parent = self.parent[value]
        if parent != value:
            self.parent[value] = self.find(parent)
        return self.parent[value]

    def union(self, left: int, right: int) -> None:
        left_root = self.find(left)
        right_root = self.find(right)
        if left_root != right_root:
            self.parent[right_root] = left_root


def _empty_source_payload(reason: str) -> dict[str, Any]:
    return {
        "status": "unavailable",
        "reason": reason,
        "n_articles": 0,
        "n_sources": 0,
        "n_lenses": 0,
        "source_counts": {},
        "permutations": 0,
        "multivariate": None,
        "classification": None,
    }


def unavailable_event_control(config: EventEmbeddingConfig, reason: str, *, total_articles: int = 0) -> dict[str, Any]:
    return {
        "status": "unavailable",
        "reason": reason,
        "config": {
            "embedding_model": config.model,
            "embedding_dimensions": config.dimensions,
            "similarity_threshold": config.threshold,
            "date_window_days": config.date_window_days,
            "cache_path": str(config.cache_path),
            "batch_size": config.batch_size,
        },
        "cache": {"enabled": bool(config.enabled), "hits": 0, "misses": 0, "stored": 0},
        "events": [],
        "same_event_source_differentiation": _empty_source_payload(reason),
        "same_event_source_lens_effects": {
            "status": "unavailable",
            "reason": reason,
            "rows": [],
            "permutations": 0,
            "multiple_testing": {"method": "benjamini-hochberg", "target": "p_perm_raw", "n_tests": 0},
        },
        "same_event_pairwise_source_lens_deltas": {
            "status": "unavailable",
            "reason": reason,
            "method": "event_source_mean_pairwise_delta_v1",
            "rows": [],
            "summary": {"source_pair_count": 0, "lens_count": 0, "row_count": 0, "event_pair_observation_count": 0},
        },
        "event_coverage": {
            "status": "unavailable",
            "reason": reason,
            "source_rows": [],
            "source_pair_rows": [],
            "summary": {
                "source_count": 0,
                "source_pair_count": 0,
                "event_article_memberships": 0,
                "multi_source_event_article_memberships": 0,
            },
        },
        "same_event_variance_decomposition": {
            "status": "unavailable",
            "reason": reason,
            "method": "event_centered_source_variance_v1",
            "rows": [],
            "summary": {"lens_count": 0, "row_count": 0, "event_count": 0, "source_count": 0},
        },
        "summary": {
            "total_articles_considered": total_articles,
            "embedded_count": 0,
            "event_count": 0,
            "multi_source_event_count": 0,
            "singleton_count": total_articles,
            "unavailable_reason": reason,
        },
    }


def _embed_with_cache(
    text_items: list[tuple[int, str, str]],
    *,
    config: EventEmbeddingConfig,
    provider: EmbeddingProvider | None,
) -> tuple[dict[int, list[float]], dict[str, int], str | None]:
    if not config.enabled:
        return {}, {"enabled": 0, "hits": 0, "misses": 0, "stored": 0}, "Event embeddings are disabled."
    if provider is None and not os.getenv("OPENAI_API_KEY"):
        return {}, {"enabled": 1, "hits": 0, "misses": 0, "stored": 0}, "OPENAI_API_KEY is not configured."

    active_provider = provider or OpenAIEmbeddingProvider()
    cache = SQLiteEmbeddingCache(config.cache_path)
    unique_by_hash: dict[str, str] = {}
    for _idx, text_hash, text in text_items:
        unique_by_hash.setdefault(text_hash, text)

    cached = cache.get_many(list(unique_by_hash.keys()), model=config.model, dimensions=config.dimensions)
    missing = [(text_hash, text) for text_hash, text in unique_by_hash.items() if text_hash not in cached]
    stored_rows: list[tuple[str, str, list[float]]] = []
    try:
        for start in range(0, len(missing), config.batch_size):
            batch = missing[start : start + config.batch_size]
            embeddings = active_provider.embed_texts(
                [text for _text_hash, text in batch],
                model=config.model,
                dimensions=config.dimensions,
            )
            if len(embeddings) != len(batch):
                return {}, {"enabled": 1, "hits": len(cached), "misses": len(missing), "stored": 0}, (
                    "Embedding provider returned an unexpected number of vectors."
                )
            for (text_hash, text), embedding in zip(batch, embeddings):
                cached[text_hash] = embedding
                stored_rows.append((text_hash, text, embedding))
    except Exception as exc:  # noqa: BLE001
        return {}, {"enabled": 1, "hits": len(cached), "misses": len(missing), "stored": 0}, str(exc)

    cache.set_many(stored_rows, model=config.model, dimensions=config.dimensions)
    by_index = {idx: cached[text_hash] for idx, text_hash, _text in text_items if text_hash in cached}
    return by_index, {"enabled": 1, "hits": len(unique_by_hash) - len(missing), "misses": len(missing), "stored": len(stored_rows)}, None


def build_event_clusters(
    records: list[dict[str, Any]],
    source_labels: list[str],
    *,
    config: EventEmbeddingConfig | None = None,
    provider: EmbeddingProvider | None = None,
) -> dict[str, Any]:
    active_config = config or event_embedding_config_from_env()
    if len(records) != len(source_labels):
        return unavailable_event_control(
            active_config,
            "Event clustering requires aligned records and source labels.",
            total_articles=len(records),
        )

    text_items: list[tuple[int, str, str]] = []
    published_by_index: dict[int, datetime | None] = {}
    for idx, record in enumerate(records):
        text = event_text_for_record(record)
        if not text:
            continue
        text_items.append((idx, _text_hash(text), text))
        published_by_index[idx] = _parse_datetime(record.get("published_at") or record.get("published"))

    embeddings, cache_stats, error = _embed_with_cache(text_items, config=active_config, provider=provider)
    if error:
        payload = unavailable_event_control(active_config, error, total_articles=len(records))
        payload["cache"] = {
            "enabled": bool(cache_stats.get("enabled")),
            "hits": cache_stats.get("hits", 0),
            "misses": cache_stats.get("misses", 0),
            "stored": cache_stats.get("stored", 0),
        }
        return payload

    indexes = sorted(embeddings.keys())
    union_find = _UnionFind(len(records))
    max_delta = timedelta(days=active_config.date_window_days)
    compared_pairs: set[tuple[int, int]] = set()

    def compare_pair(left_idx: int, right_idx: int) -> None:
        key = (left_idx, right_idx) if left_idx < right_idx else (right_idx, left_idx)
        if key in compared_pairs:
            return
        compared_pairs.add(key)
        similarity = _cosine_similarity(embeddings[left_idx], embeddings[right_idx])
        if similarity is not None and similarity >= active_config.threshold:
            union_find.union(left_idx, right_idx)

    dated_indexes = [
        (idx, published_by_index[idx])
        for idx in indexes
        if published_by_index.get(idx) is not None
    ]
    dated_indexes.sort(key=lambda item: item[1])
    for left_pos, (left_idx, left_dt) in enumerate(dated_indexes):
        for right_idx, right_dt in dated_indexes[left_pos + 1 :]:
            if right_dt - left_dt > max_delta:
                break
            compare_pair(left_idx, right_idx)

    undated_indexes = [idx for idx in indexes if published_by_index.get(idx) is None]
    undated_positions = {idx: pos for pos, idx in enumerate(undated_indexes)}
    for left_pos, left_idx in enumerate(undated_indexes):
        for right_idx in indexes:
            if right_idx == left_idx:
                continue
            right_pos = undated_positions.get(right_idx)
            if right_pos is not None and right_pos <= left_pos:
                continue
            compare_pair(left_idx, right_idx)

    grouped: dict[int, list[int]] = {}
    for idx in indexes:
        grouped.setdefault(union_find.find(idx), []).append(idx)

    events: list[dict[str, Any]] = []
    event_member_indexes: list[list[int]] = []
    singleton_count = 0
    multi_source_event_count = 0
    for member_indexes in grouped.values():
        member_indexes = sorted(member_indexes)
        if len(member_indexes) < 2:
            singleton_count += 1
            continue

        event_records = [records[idx] for idx in member_indexes]
        source_counts = Counter(source_labels[idx] for idx in member_indexes)
        if len(source_counts) >= 2:
            multi_source_event_count += 1

        topic_counter: Counter[str] = Counter()
        tag_counter: Counter[str] = Counter()
        dates: list[str] = []
        titles: list[str] = []
        article_ids: list[str] = []
        for record in event_records:
            title = _clean_text(record.get("title"))
            if title:
                titles.append(title)
            article_id = _clean_text(record.get("id")) or _clean_text(record.get("link"))
            if article_id:
                article_ids.append(article_id)
            parsed_dt = _parse_datetime(record.get("published_at") or record.get("published"))
            if parsed_dt is not None:
                dates.append(parsed_dt.date().isoformat())
            for topic in record.get("topic_tags") if isinstance(record.get("topic_tags"), list) else []:
                text = _clean_text(topic)
                if text:
                    topic_counter[text] += 1
            for tag in record.get("tags") if isinstance(record.get("tags"), list) else []:
                text = _clean_text(tag)
                if text:
                    tag_counter[text] += 1

        event_seed = "|".join(article_ids or [str(idx) for idx in member_indexes])
        event_id = f"event-{hashlib.sha1(event_seed.encode('utf-8')).hexdigest()[:12]}"
        events.append(
            {
                "event_id": event_id,
                "representative_title": titles[0] if titles else "Untitled event",
                "date_start": min(dates) if dates else None,
                "date_end": max(dates) if dates else None,
                "article_count": len(member_indexes),
                "source_counts": dict(sorted(source_counts.items(), key=lambda item: (-item[1], item[0].lower()))),
                "sources": sorted(source_counts.keys(), key=lambda value: value.lower()),
                "topic_counts": dict(topic_counter.most_common()),
                "tag_counts": dict(tag_counter.most_common()),
                "article_ids": article_ids,
            }
        )
        event_member_indexes.append(member_indexes)

    sorted_pairs = sorted(zip(events, event_member_indexes), key=lambda item: (-item[0]["article_count"], str(item[0]["representative_title"]).lower()))
    events = [event for event, _member_indexes in sorted_pairs]
    event_member_indexes = [member_indexes for _event, member_indexes in sorted_pairs]

    return {
        "status": "ok",
        "reason": "",
        "config": {
            "embedding_model": active_config.model,
            "embedding_dimensions": active_config.dimensions,
            "similarity_threshold": active_config.threshold,
            "date_window_days": active_config.date_window_days,
            "cache_path": str(active_config.cache_path),
            "batch_size": active_config.batch_size,
        },
        "cache": {
            "enabled": bool(cache_stats.get("enabled")),
            "hits": cache_stats.get("hits", 0),
            "misses": cache_stats.get("misses", 0),
            "stored": cache_stats.get("stored", 0),
        },
        "events": events,
        "_event_member_indexes": event_member_indexes,
        "summary": {
            "total_articles_considered": len(records),
            "embedded_count": len(embeddings),
            "event_count": len(events),
            "multi_source_event_count": multi_source_event_count,
            "singleton_count": singleton_count,
            "unavailable_reason": None,
        },
    }
