import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from src.analytics.news_event_control import EventEmbeddingConfig, build_event_clusters
from src.services import rss_digest


class CountingEmbeddingProvider:
    def __init__(self, vectors_by_marker: dict[str, list[float]]) -> None:
        self.vectors_by_marker = vectors_by_marker
        self.calls = 0
        self.requested_texts: list[str] = []

    def embed_texts(self, texts: list[str], *, model: str, dimensions: int) -> list[list[float]]:
        self.calls += 1
        self.requested_texts.extend(texts)
        vectors: list[list[float]] = []
        for text in texts:
            for marker, vector in self.vectors_by_marker.items():
                if marker in text:
                    vectors.append(vector)
                    break
            else:
                vectors.append([0.0, 1.0, 0.0])
        return vectors


def _config(cache_path: Path, *, enabled: bool = True, threshold: float = 0.86, window_days: int = 3) -> EventEmbeddingConfig:
    return EventEmbeddingConfig(
        enabled=enabled,
        model="test-embedding-model",
        dimensions=3,
        threshold=threshold,
        date_window_days=window_days,
        cache_path=cache_path,
        batch_size=2,
    )


def _record(
    article_id: str,
    title: str,
    published_at: str = "2026-03-01T12:00:00Z",
    topic_tags: list[str] | None = None,
    tags: list[str] | None = None,
) -> dict:
    return {
        "id": article_id,
        "title": title,
        "ai_summary": f"{title} summary",
        "summary": f"{title} public summary",
        "published_at": published_at,
        "topic_tags": topic_tags or ["Policy"],
        "tags": tags or ["OpenAI"],
    }


class NewsEventControlTests(unittest.TestCase):
    def test_embedding_cache_skips_second_provider_call(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            cache_path = Path(tmpdir) / "events.sqlite"
            provider = CountingEmbeddingProvider({"Shared": [1.0, 0.0, 0.0]})
            records = [
                _record("a1", "Shared event from source A"),
                _record("a2", "Shared event from source B"),
            ]
            config = _config(cache_path)

            first = build_event_clusters(records, ["A", "B"], config=config, provider=provider)
            second = build_event_clusters(records, ["A", "B"], config=config, provider=provider)

            self.assertEqual(first["status"], "ok")
            self.assertEqual(second["status"], "ok")
            self.assertEqual(provider.calls, 1)
            self.assertEqual(first["cache"]["misses"], 2)
            self.assertEqual(second["cache"]["hits"], 2)
            self.assertEqual(second["cache"]["misses"], 0)

    def test_missing_api_key_marks_event_control_unavailable(self):
        previous_key = os.environ.pop("OPENAI_API_KEY", None)
        try:
            with tempfile.TemporaryDirectory() as tmpdir:
                payload = build_event_clusters(
                    [_record("a1", "Uncached event")],
                    ["A"],
                    config=_config(Path(tmpdir) / "events.sqlite"),
                )
            self.assertEqual(payload["status"], "unavailable")
            self.assertIn("OPENAI_API_KEY", payload["reason"])
            self.assertEqual(payload["summary"]["unavailable_reason"], payload["reason"])
        finally:
            if previous_key is not None:
                os.environ["OPENAI_API_KEY"] = previous_key

    def test_synthetic_embeddings_cluster_same_event_and_gate_by_date(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            records = [
                _record("a1", "Launch story A", "2026-03-01T10:00:00Z"),
                _record("a2", "Launch story B", "2026-03-02T10:00:00Z"),
                _record("a3", "Unrelated finance story", "2026-03-02T10:00:00Z"),
                _record("a4", "Launch story old", "2026-04-10T10:00:00Z"),
            ]
            provider = CountingEmbeddingProvider(
                {
                    "Launch": [1.0, 0.0, 0.0],
                    "Unrelated": [0.0, 1.0, 0.0],
                }
            )
            payload = build_event_clusters(
                records,
                ["A", "B", "C", "D"],
                config=_config(Path(tmpdir) / "events.sqlite", window_days=3),
                provider=provider,
            )

        self.assertEqual(payload["status"], "ok")
        self.assertEqual(payload["summary"]["event_count"], 1)
        self.assertEqual(payload["summary"]["multi_source_event_count"], 1)
        self.assertEqual(payload["summary"]["singleton_count"], 2)
        event = payload["events"][0]
        self.assertEqual(event["article_count"], 2)
        self.assertEqual(event["source_counts"], {"A": 1, "B": 1})
        self.assertEqual(event["article_ids"], ["a1", "a2"])

    def test_same_event_adapter_feeds_source_comparisons_from_multisource_clusters(self):
        fake_clusters = {
            "status": "ok",
            "reason": "",
            "config": {},
            "cache": {"enabled": True, "hits": 0, "misses": 0, "stored": 0},
            "events": [
                {
                    "event_id": "event-shared",
                    "article_count": 4,
                    "source_counts": {"A": 2, "B": 2},
                },
                {
                    "event_id": "event-single-source",
                    "article_count": 2,
                    "source_counts": {"A": 2},
                },
            ],
            "_event_member_indexes": [[0, 1, 2, 3], [4, 5]],
            "summary": {
                "total_articles_considered": 6,
                "embedded_count": 6,
                "event_count": 2,
                "multi_source_event_count": 1,
                "singleton_count": 0,
                "unavailable_reason": None,
            },
        }
        rows = [
            {"Evidence": 90.0},
            {"Evidence": 20.0},
            {"Evidence": 85.0},
            {"Evidence": 25.0},
            {"Evidence": 95.0},
            {"Evidence": 90.0},
        ]
        sources = ["A", "B", "A", "B", "A", "A"]

        with patch.object(rss_digest, "build_event_clusters", return_value=fake_clusters):
            payload = rss_digest._event_control_from_records(rows, sources, [{} for _ in rows], ["Evidence"])

        self.assertEqual(payload["status"], "ok")
        self.assertNotIn("_event_member_indexes", payload)
        self.assertEqual(payload["same_event_source_differentiation"]["source_counts"], {"A": 2, "B": 2})
        effects_rows = payload["same_event_source_lens_effects"]["rows"]
        self.assertEqual(effects_rows[0]["lens"], "Evidence")
        self.assertEqual(effects_rows[0]["source_counts"], {"A": 2, "B": 2})
        deltas = payload["same_event_pairwise_source_lens_deltas"]
        self.assertEqual(deltas["status"], "ok")
        self.assertEqual(deltas["summary"]["source_pair_count"], 1)
        self.assertEqual(deltas["summary"]["lens_count"], 1)
        self.assertEqual(deltas["rows"][0]["source_a"], "A")
        self.assertEqual(deltas["rows"][0]["source_b"], "B")
        self.assertEqual(deltas["rows"][0]["lens"], "Evidence")
        self.assertEqual(deltas["rows"][0]["n_events"], 1)
        self.assertAlmostEqual(deltas["rows"][0]["mean_delta_a_minus_b"], 65.0)
        coverage = payload["event_coverage"]
        self.assertEqual(coverage["status"], "ok")
        self.assertEqual(coverage["summary"]["source_count"], 2)
        self.assertEqual(coverage["summary"]["source_pair_count"], 1)
        self.assertEqual(coverage["source_pair_rows"][0]["source_a"], "A")
        self.assertEqual(coverage["source_pair_rows"][0]["source_b"], "B")
        self.assertEqual(coverage["source_pair_rows"][0]["shared_event_count"], 1)
        variance = payload["same_event_variance_decomposition"]
        self.assertEqual(variance["status"], "ok")
        self.assertEqual(variance["summary"]["lens_count"], 1)
        self.assertEqual(variance["rows"][0]["lens"], "Evidence")
        self.assertEqual(variance["rows"][0]["event_count"], 1)
        self.assertEqual(variance["rows"][0]["source_count"], 2)
        self.assertIn("source_eta_sq_event_centered", variance["rows"][0])


if __name__ == "__main__":
    unittest.main()
