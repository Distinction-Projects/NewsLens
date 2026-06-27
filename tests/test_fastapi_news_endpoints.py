import csv
import io
import json
import os
import shutil
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.api.fastapi_news import register_fastapi_news_endpoints


NOW_UTC = datetime.now(timezone.utc)
NOW_UTC_ISO = NOW_UTC.isoformat().replace("+00:00", "Z")
DIGEST_UTC_ISO = (NOW_UTC - timedelta(minutes=3)).isoformat().replace("+00:00", "Z")


SAMPLE_PAYLOAD = {
    "schema_version": "1.0",
    "generated_at": NOW_UTC_ISO,
    "contract": "rss_pipeline_precomputed",
    "digest": {
        "generated_at": DIGEST_UTC_ISO,
        "run_id": "digest-fastapi-abc123",
    },
    "summary": {"articles": 3, "scored_articles": 3},
    "analysis": {"lens_summary": {}, "source_differentiation": {}},
    "articles": [
        {
            "id": "a-1",
            "title": "Latest Story",
            "link": "https://example.com/latest",
            "published": "Mon, 02 Mar 2026 15:25:29 -0500",
            "summary": "Summary 1",
            "ai_summary": "AI Summary 1",
            "ai_tags": ["OpenAI", "Policy"],
            "topic_tags": ["General"],
            "source": {"id": "pbs-newshour", "name": "PBS NewsHour"},
            "feed": {"name": "Headlines", "url": "https://example.com/feed"},
            "scraped": {"title": "Latest Story", "body_text": "Body"},
            "scrape_error": None,
            "score": {
                "value": 14.0,
                "max_value": 20.0,
                "percent": 70.0,
                "rubric_count": 3,
                "lens_scores": {"L1": {"percent": 70.0}},
            },
        },
        {
            "id": "a-2",
            "title": "Older Story",
            "link": "https://example.com/older",
            "published": "2026-03-01T03:10:00Z",
            "summary": "Summary 2",
            "ai_summary": "AI Summary 2",
            "ai_tags": ["Science"],
            "topic_tags": ["OpenAI"],
            "source": {"id": "npr", "name": "NPR"},
            "feed": {"name": "World", "url": "https://example.com/world"},
            "scraped": {"title": "Older Story", "body_text": "Body"},
            "scrape_error": None,
            "score": {"value": 8.0, "max_value": 20.0, "percent": 40.0, "rubric_count": 3},
        },
        {
            "id": "a-3",
            "title": "Failed Scrape Story",
            "link": "https://example.com/failed",
            "published": "2026-03-03T03:10:00Z",
            "summary": "Summary 3",
            "ai_summary": "AI Summary 3",
            "ai_tags": ["OpenAI"],
            "topic_tags": ["General"],
            "source": {"id": "failed-source", "name": "Failed Source"},
            "feed": {"name": "Errors", "url": "https://example.com/errors"},
            "scraped": None,
            "scrape_error": "HTTP 500",
            "score": {"value": 20.0, "max_value": 20.0, "percent": 100.0, "rubric_count": 3},
        },
    ],
}


def _coverage_gap_temporal_payload() -> dict:
    articles = []
    article_specs = [
        ("2026-04-01", "Source A", ["Policy"], ["Risk"], 82.0, 24.0, 28.0),
        ("2026-04-03", "Source A", ["Policy"], ["Risk"], 80.0, 26.0, 30.0),
        ("2026-04-02", "Source B", ["Markets"], ["Growth"], 44.0, 76.0, 38.0),
        ("2026-04-04", "Source B", ["Markets"], ["Growth"], 42.0, 78.0, 40.0),
        ("2026-04-07", "Source B", ["Markets"], ["Growth"], 46.0, 74.0, 42.0),
        ("2026-04-09", "Source B", ["Markets"], ["Growth"], 48.0, 72.0, 44.0),
        ("2026-04-14", "Source A", ["Policy"], ["Risk"], 76.0, 30.0, 34.0),
        ("2026-04-16", "Source A", ["Policy"], ["Risk"], 74.0, 32.0, 36.0),
        ("2026-04-15", "Source B", ["Markets"], ["Growth"], 50.0, 70.0, 46.0),
        ("2026-04-17", "Source B", ["Markets"], ["Growth"], 52.0, 68.0, 48.0),
    ]
    for idx, (published, source_name, topic_tags, ai_tags, evidence, impact, novelty) in enumerate(article_specs):
        articles.append(
            {
                "id": f"coverage-gap-endpoint-{idx}",
                "title": f"Coverage gap endpoint {idx}",
                "link": f"https://example.com/coverage-gap/{idx}",
                "published": f"{published}T00:00:00Z",
                "summary": f"Summary {idx}",
                "ai_summary": f"AI Summary {idx}",
                "ai_tags": ai_tags,
                "topic_tags": topic_tags,
                "source": {"id": source_name.lower().replace(' ', '-'), "name": source_name},
                "feed": {"name": "Feed", "url": "https://example.com/feed"},
                "scraped": {"title": f"Coverage gap endpoint {idx}", "body_text": "Body"},
                "scrape_error": None,
                "score": {
                    "value": 15.0,
                    "max_value": 20.0,
                    "percent": 75.0,
                    "rubric_count": 3,
                    "lens_scores": {
                        "Evidence": {"percent": evidence},
                        "Impact": {"percent": impact},
                        "Novelty": {"percent": novelty},
                    },
                },
            }
        )

    return {
        "schema_version": "1.0",
        "generated_at": NOW_UTC_ISO,
        "contract": "rss_pipeline_precomputed",
        "digest": {
            "generated_at": DIGEST_UTC_ISO,
            "run_id": "digest-fastapi-coverage-gap",
        },
        "summary": {"articles": len(articles), "scored_articles": len(articles)},
        "analysis": {
            "lens_summary": {
                "lenses": [
                    {"name": "Evidence", "max_total": 10.0},
                    {"name": "Impact", "max_total": 10.0},
                    {"name": "Novelty", "max_total": 10.0},
                ]
            },
            "source_differentiation": {},
        },
        "articles": articles,
    }


def _multi_week_coverage_gap_temporal_payload() -> dict:
    articles = []
    article_specs = [
        ("2026-03-31", "Source A", ["Policy"], ["Risk"], 82.0, 24.0, 28.0),
        ("2026-04-02", "Source A", ["Policy"], ["Risk"], 80.0, 26.0, 30.0),
        ("2026-04-01", "Source B", ["Markets"], ["Growth"], 44.0, 76.0, 38.0),
        ("2026-04-03", "Source B", ["Markets"], ["Growth"], 42.0, 78.0, 40.0),
        ("2026-04-07", "Source B", ["Markets"], ["Growth"], 46.0, 74.0, 42.0),
        ("2026-04-09", "Source B", ["Markets"], ["Growth"], 48.0, 72.0, 44.0),
        ("2026-04-14", "Source B", ["Markets"], ["Growth"], 50.0, 70.0, 46.0),
        ("2026-04-16", "Source B", ["Markets"], ["Growth"], 52.0, 68.0, 48.0),
        ("2026-04-21", "Source A", ["Policy"], ["Risk"], 76.0, 30.0, 34.0),
        ("2026-04-23", "Source A", ["Policy"], ["Risk"], 74.0, 32.0, 36.0),
        ("2026-04-22", "Source B", ["Markets"], ["Growth"], 54.0, 66.0, 50.0),
        ("2026-04-24", "Source B", ["Markets"], ["Growth"], 56.0, 64.0, 52.0),
    ]
    for idx, (published, source_name, topic_tags, ai_tags, evidence, impact, novelty) in enumerate(article_specs):
        articles.append(
            {
                "id": f"coverage-gap-range-endpoint-{idx}",
                "title": f"Coverage gap range endpoint {idx}",
                "link": f"https://example.com/coverage-gap-range/{idx}",
                "published": f"{published}T00:00:00Z",
                "summary": f"Summary {idx}",
                "ai_summary": f"AI Summary {idx}",
                "ai_tags": ai_tags,
                "topic_tags": topic_tags,
                "source": {"id": source_name.lower().replace(' ', '-'), "name": source_name},
                "feed": {"name": "Feed", "url": "https://example.com/feed"},
                "scraped": {"title": f"Coverage gap range endpoint {idx}", "body_text": "Body"},
                "scrape_error": None,
                "score": {
                    "value": 15.0,
                    "max_value": 20.0,
                    "percent": 75.0,
                    "rubric_count": 3,
                    "lens_scores": {
                        "Evidence": {"percent": evidence},
                        "Impact": {"percent": impact},
                        "Novelty": {"percent": novelty},
                    },
                },
            }
        )

    return {
        "schema_version": "1.0",
        "generated_at": NOW_UTC_ISO,
        "contract": "rss_pipeline_precomputed",
        "digest": {
            "generated_at": DIGEST_UTC_ISO,
            "run_id": "digest-fastapi-coverage-gap-range",
        },
        "summary": {"articles": len(articles), "scored_articles": len(articles)},
        "analysis": {
            "lens_summary": {
                "lenses": [
                    {"name": "Evidence", "max_total": 10.0},
                    {"name": "Impact", "max_total": 10.0},
                    {"name": "Novelty", "max_total": 10.0},
                ]
            },
            "source_differentiation": {},
        },
        "articles": articles,
    }


def _sparse_bucket_temporal_payload() -> dict:
    articles = []
    article_specs = [
        ("2026-03-31", "Source A", ["Policy"], ["Risk"], 82.0, 24.0, 28.0),
        ("2026-04-02", "Source A", ["Policy"], ["Risk"], 80.0, 26.0, 30.0),
        ("2026-04-08", "Source A", ["Policy"], ["Risk"], 78.0, 28.0, 32.0),
        ("2026-04-22", "Source A", ["Policy"], ["Risk"], 76.0, 30.0, 34.0),
        ("2026-04-24", "Source A", ["Policy"], ["Risk"], 74.0, 32.0, 36.0),
        ("2026-04-01", "Source B", ["Markets"], ["Growth"], 44.0, 76.0, 38.0),
        ("2026-04-03", "Source B", ["Markets"], ["Growth"], 42.0, 78.0, 40.0),
        ("2026-04-07", "Source B", ["Markets"], ["Growth"], 46.0, 74.0, 42.0),
        ("2026-04-09", "Source B", ["Markets"], ["Growth"], 48.0, 72.0, 44.0),
        ("2026-04-14", "Source B", ["Markets"], ["Growth"], 50.0, 70.0, 46.0),
        ("2026-04-16", "Source B", ["Markets"], ["Growth"], 52.0, 68.0, 48.0),
        ("2026-04-21", "Source B", ["Markets"], ["Growth"], 54.0, 66.0, 50.0),
        ("2026-04-23", "Source B", ["Markets"], ["Growth"], 56.0, 64.0, 52.0),
    ]
    for idx, (published, source_name, topic_tags, ai_tags, evidence, impact, novelty) in enumerate(article_specs):
        articles.append(
            {
                "id": f"sparse-bucket-endpoint-{idx}",
                "title": f"Sparse bucket endpoint {idx}",
                "link": f"https://example.com/sparse-bucket/{idx}",
                "published": f"{published}T00:00:00Z",
                "summary": f"Summary {idx}",
                "ai_summary": f"AI Summary {idx}",
                "ai_tags": ai_tags,
                "topic_tags": topic_tags,
                "source": {"id": source_name.lower().replace(' ', '-'), "name": source_name},
                "feed": {"name": "Feed", "url": "https://example.com/feed"},
                "scraped": {"title": f"Sparse bucket endpoint {idx}", "body_text": "Body"},
                "scrape_error": None,
                "score": {
                    "value": 15.0,
                    "max_value": 20.0,
                    "percent": 75.0,
                    "rubric_count": 3,
                    "lens_scores": {
                        "Evidence": {"percent": evidence},
                        "Impact": {"percent": impact},
                        "Novelty": {"percent": novelty},
                    },
                },
            }
        )

    return {
        "schema_version": "1.0",
        "generated_at": NOW_UTC_ISO,
        "contract": "rss_pipeline_precomputed",
        "digest": {
            "generated_at": DIGEST_UTC_ISO,
            "run_id": "digest-fastapi-sparse-bucket",
        },
        "summary": {"articles": len(articles), "scored_articles": len(articles)},
        "analysis": {
            "lens_summary": {
                "lenses": [
                    {"name": "Evidence", "max_total": 10.0},
                    {"name": "Impact", "max_total": 10.0},
                    {"name": "Novelty", "max_total": 10.0},
                ]
            },
            "source_differentiation": {},
        },
        "articles": articles,
    }


def _sparse_bucket_temporal_payload_with_multi_word_topic() -> dict:
    payload = _sparse_bucket_temporal_payload()
    for article in payload.get("articles", []):
        if not isinstance(article, dict):
            continue
        if article.get("topic_tags") == ["Policy"]:
            article["topic_tags"] = ["Climate Risk"]
    return payload


class FastApiNewsEndpointTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp_dir = Path(tempfile.mkdtemp(prefix="rss-fastapi-endpoints-"))
        cls.current_payload_path = cls.temp_dir / "rss_openai_precomputed.json"
        cls.current_payload_path.write_text(json.dumps(SAMPLE_PAYLOAD), encoding="utf-8")

        cls.snapshot_date = "2026-03-10"
        cls.snapshot_payload_path = cls.temp_dir / f"rss_openai_daily_{cls.snapshot_date}.json"
        cls.snapshot_payload_path.write_text(json.dumps(SAMPLE_PAYLOAD), encoding="utf-8")

        os.environ["RSS_DAILY_JSON_URL"] = f"file://{cls.current_payload_path}"
        os.environ["RSS_HISTORY_JSON_URL_TEMPLATE"] = f"file://{cls.temp_dir}/rss_openai_daily_{{date}}.json"
        os.environ["RSS_CACHE_TTL_SECONDS"] = "60"
        os.environ["RSS_HTTP_TIMEOUT_SECONDS"] = "5"
        os.environ["RSS_MAX_AGE_SECONDS"] = "172800"

        app = FastAPI()
        register_fastapi_news_endpoints(app)
        cls.client = TestClient(app)

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.temp_dir, ignore_errors=True)

    def test_digest_latest_and_invalid_limit(self):
        digest = self.client.get("/api/news/digest")
        self.assertEqual(digest.status_code, 200)
        payload = digest.json()
        self.assertEqual(payload["status"], "ok")
        self.assertEqual(len(payload["data"]), 2)
        self.assertEqual(payload["meta"]["input_articles_count"], 3)
        self.assertEqual(payload["meta"]["excluded_unscraped_articles"], 1)

        latest = self.client.get("/api/news/digest/latest")
        self.assertEqual(latest.status_code, 200)
        self.assertEqual(latest.json()["data"]["id"], "a-1")

        bad_limit = self.client.get("/api/news/digest?limit=0")
        self.assertEqual(bad_limit.status_code, 400)
        self.assertEqual(bad_limit.json()["status"], "bad_request")

    def test_stats_and_snapshot_mode(self):
        stats = self.client.get("/api/news/stats")
        self.assertEqual(stats.status_code, 200)
        payload = stats.json()
        self.assertEqual(payload["status"], "ok")
        self.assertIn("derived", payload["data"])
        self.assertIn("source_topic_control", payload["data"]["derived"])
        self.assertIn("tag_sliced_analysis", payload["data"]["derived"])
        self.assertIn("tag_momentum", payload["data"]["derived"])
        self.assertIn("group_latent_space", payload["data"]["derived"])
        self.assertIn("group_temporal_latent_space", payload["data"]["derived"])
        self.assertIn("tag_lens_pca", payload["data"]["derived"])
        self.assertIn("event_control", payload["data"]["derived"])

        snapshot = self.client.get(f"/api/news/stats?snapshot_date={self.snapshot_date}")
        self.assertEqual(snapshot.status_code, 200)
        snapshot_payload = snapshot.json()
        self.assertEqual(snapshot_payload["meta"]["source_mode"], "snapshot")
        self.assertEqual(snapshot_payload["meta"]["snapshot_date"], self.snapshot_date)

        missing_snapshot = self.client.get("/api/news/stats?snapshot_date=2026-03-09")
        self.assertEqual(missing_snapshot.status_code, 404)
        self.assertEqual(missing_snapshot.json()["status"], "not_found")

    def test_stats_serializes_group_temporal_coverage_gap_metrics(self):
        original_payload = self.current_payload_path.read_text(encoding="utf-8")
        try:
            self.current_payload_path.write_text(json.dumps(_coverage_gap_temporal_payload()), encoding="utf-8")
            stats = self.client.get("/api/news/stats?refresh=1")
            self.assertEqual(stats.status_code, 200)

            payload = stats.json()
            temporal = payload["data"]["derived"]["group_temporal_latent_space"]
            self.assertEqual(temporal["summary"]["bucket_count"], 3)

            if temporal["status"] == "unavailable":
                self.assertIn("pca", str(temporal.get("reason", "")).lower())
                return

            by_source = {row["group"]: row for row in temporal["groups"]["source"]}
            by_topic = {row["group"]: row for row in temporal["groups"]["topic"]}
            by_tag = {row["group"]: row for row in temporal["groups"]["tag"]}

            self.assertEqual(
                [bucket["bucket_start"] for bucket in by_source["Source A"]["buckets"]],
                ["2026-03-30", "2026-04-13"],
            )
            source_a_popularity = by_source["Source A"]["popularity_summary"]
            self.assertEqual(source_a_popularity["peak_bucket"], "2026-03-30")
            self.assertEqual(source_a_popularity["peak_articles"], 2)
            self.assertEqual(source_a_popularity["first_share"], 0.5)
            self.assertEqual(source_a_popularity["latest_share"], 0.5)
            self.assertEqual(source_a_popularity["share_delta"], 0.0)
            self.assertEqual(source_a_popularity["recent_share_delta"], 0.0)
            self.assertEqual(source_a_popularity["share_direction"], "flat")
            self.assertEqual(source_a_popularity["recent_share_direction"], "flat")
            self.assertEqual(source_a_popularity["momentum_label"], "flat")
            self.assertIn("first_share_rank", source_a_popularity)
            self.assertIn("latest_share_rank", source_a_popularity)
            self.assertIn("rank_change", source_a_popularity)
            self.assertEqual(by_source["Source A"]["path_summary"]["coverage_gap_count"], 1)
            self.assertEqual(
                by_source["Source A"]["path_summary"]["coverage_gap_ranges"][0],
                {
                    "start_bucket": "2026-04-06",
                    "end_bucket": "2026-04-06",
                    "missing_bucket_count": 1,
                    "label": "2026-04-06",
                },
            )
            self.assertEqual(by_source["Source B"]["path_summary"]["coverage_gap_count"], 0)
            self.assertEqual(by_topic["Policy"]["path_summary"]["coverage_gap_count"], 1)
            self.assertEqual(by_topic["Markets"]["path_summary"]["coverage_gap_count"], 0)
            self.assertEqual(by_tag["Risk"]["path_summary"]["coverage_gap_count"], 1)
            self.assertEqual(by_tag["Growth"]["path_summary"]["coverage_gap_count"], 0)
        finally:
            self.current_payload_path.write_text(original_payload, encoding="utf-8")
            self.client.get("/api/news/stats?refresh=1")

    def test_stats_serializes_multi_week_coverage_gap_ranges(self):
        original_payload = self.current_payload_path.read_text(encoding="utf-8")
        try:
            self.current_payload_path.write_text(json.dumps(_multi_week_coverage_gap_temporal_payload()), encoding="utf-8")
            stats = self.client.get("/api/news/stats?refresh=1")
            self.assertEqual(stats.status_code, 200)

            payload = stats.json()
            temporal = payload["data"]["derived"]["group_temporal_latent_space"]
            self.assertEqual(temporal["summary"]["bucket_count"], 4)

            if temporal["status"] == "unavailable":
                self.assertIn("pca", str(temporal.get("reason", "")).lower())
                return

            by_source = {row["group"]: row for row in temporal["groups"]["source"]}
            source_a = by_source["Source A"]
            self.assertEqual(
                [bucket["bucket_start"] for bucket in source_a["buckets"]],
                ["2026-03-30", "2026-04-20"],
            )
            self.assertEqual(source_a["path_summary"]["coverage_gap_count"], 1)
            self.assertEqual(
                source_a["path_summary"]["coverage_gap_ranges"][0],
                {
                    "start_bucket": "2026-04-06",
                    "end_bucket": "2026-04-13",
                    "missing_bucket_count": 2,
                    "label": "2026-04-06 to 2026-04-13",
                },
            )
        finally:
            self.current_payload_path.write_text(original_payload, encoding="utf-8")
            self.client.get("/api/news/stats?refresh=1")

    def test_export_group_temporal_path_summary_surfaces_coverage_gap_ranges(self):
        original_payload = self.current_payload_path.read_text(encoding="utf-8")
        try:
            self.current_payload_path.write_text(json.dumps(_multi_week_coverage_gap_temporal_payload()), encoding="utf-8")
            exported = self.client.get("/api/news/export?artifact=group_temporal_path_summary&format=json&refresh=1")
            self.assertEqual(exported.status_code, 200)

            payload = exported.json()
            self.assertEqual(payload["artifact"], "group_temporal_path_summary")
            self.assertIsInstance(payload["rows"], list)

            source_a = next(
                row
                for row in payload["rows"]
                if row["group_type"] == "source" and row["group"] == "Source A"
            )
            self.assertEqual(source_a["coverage_gap_count"], 1)
            self.assertEqual(source_a["coverage_gap_labels"], "2026-04-06 to 2026-04-13")
            self.assertIn("\"missing_bucket_count\": 2", source_a["coverage_gap_ranges_json"])
            self.assertEqual(source_a["bucket_granularity"], "week")
            self.assertEqual(source_a["movement_pattern_pca"], "jump-led")
            self.assertEqual(source_a["largest_jump_share_pca"], 1.0)
            self.assertEqual(source_a["popularity_peak_bucket"], "2026-03-30")
            self.assertEqual(source_a["popularity_peak_articles"], 2)
            self.assertEqual(source_a["popularity_latest_share"], 0.5)
        finally:
            self.current_payload_path.write_text(original_payload, encoding="utf-8")
            self.client.get("/api/news/stats?refresh=1")

    def test_export_group_temporal_buckets_surfaces_sparse_bucket_rows(self):
        original_payload = self.current_payload_path.read_text(encoding="utf-8")
        try:
            self.current_payload_path.write_text(json.dumps(_sparse_bucket_temporal_payload()), encoding="utf-8")
            exported = self.client.get("/api/news/export?artifact=group_temporal_buckets&format=json&refresh=1")
            self.assertEqual(exported.status_code, 200)

            payload = exported.json()
            self.assertEqual(payload["artifact"], "group_temporal_buckets")
            self.assertIsInstance(payload["rows"], list)

            sparse_row = next(
                row
                for row in payload["rows"]
                if row["group_type"] == "source" and row["group"] == "Source A" and row["bucket_status"] == "sparse"
            )
            self.assertEqual(sparse_row["bucket_start"], "2026-04-06")
            self.assertEqual(sparse_row["bucket_n_articles"], 1)
            self.assertEqual(sparse_row["group_sparse_bucket_count"], 1)
            self.assertEqual(sparse_row["group_coverage_gap_count"], 1)
            self.assertEqual(sparse_row["group_coverage_gap_labels"], "2026-04-13")
            self.assertEqual(sparse_row["group_movement_pattern_pca"], "jump-led")
            self.assertEqual(sparse_row["group_largest_jump_share_pca"], 1.0)
            self.assertIn("\"Source A\": 1", sparse_row["bucket_source_counts_json"])
        finally:
            self.current_payload_path.write_text(original_payload, encoding="utf-8")
            self.client.get("/api/news/stats?refresh=1")

    def test_export_group_temporal_buckets_accepts_group_filters(self):
        original_payload = self.current_payload_path.read_text(encoding="utf-8")
        try:
            self.current_payload_path.write_text(json.dumps(_sparse_bucket_temporal_payload()), encoding="utf-8")
            exported = self.client.get(
                "/api/news/export?artifact=group_temporal_buckets&format=json&refresh=1&group_type=source&group_key=source-a"
            )
            self.assertEqual(exported.status_code, 200)

            payload = exported.json()
            self.assertEqual(payload["filters"], {"group_type": "source", "group_key": "source-a"})
            self.assertTrue(payload["rows"])
            self.assertTrue(all(row["group_type"] == "source" for row in payload["rows"]))
            self.assertTrue(all(row["group"] == "Source A" for row in payload["rows"]))
        finally:
            self.current_payload_path.write_text(original_payload, encoding="utf-8")
            self.client.get("/api/news/stats?refresh=1")

    def test_export_group_temporal_path_summary_accepts_topic_group_filters_with_popularity_fields(self):
        original_payload = self.current_payload_path.read_text(encoding="utf-8")
        try:
            self.current_payload_path.write_text(json.dumps(_sparse_bucket_temporal_payload()), encoding="utf-8")
            exported = self.client.get(
                "/api/news/export?artifact=group_temporal_path_summary&format=json&refresh=1&group_type=topic&group_key=policy"
            )
            self.assertEqual(exported.status_code, 200)

            payload = exported.json()
            self.assertEqual(payload["filters"], {"group_type": "topic", "group_key": "policy"})
            self.assertEqual(len(payload["rows"]), 1)
            self.assertEqual(payload["rows"][0]["group"], "Policy")
            self.assertEqual(payload["rows"][0]["popularity_peak_bucket"], "2026-03-30")
            self.assertEqual(payload["rows"][0]["popularity_peak_articles"], 2)
            self.assertEqual(payload["rows"][0]["popularity_first_share"], 0.5)
            self.assertEqual(payload["rows"][0]["popularity_latest_share"], 0.5)
            self.assertAlmostEqual(payload["rows"][0]["popularity_recent_share_delta"], 1 / 6)
        finally:
            self.current_payload_path.write_text(original_payload, encoding="utf-8")
            self.client.get("/api/news/stats?refresh=1")

    def test_export_group_temporal_path_summary_accepts_group_filters(self):
        original_payload = self.current_payload_path.read_text(encoding="utf-8")
        try:
            self.current_payload_path.write_text(json.dumps(_sparse_bucket_temporal_payload()), encoding="utf-8")
            exported = self.client.get(
                "/api/news/export?artifact=group_temporal_path_summary&format=json&refresh=1&group_type=source&group_key=source-a"
            )
            self.assertEqual(exported.status_code, 200)

            payload = exported.json()
            self.assertEqual(payload["filters"], {"group_type": "source", "group_key": "source-a"})
            self.assertEqual(len(payload["rows"]), 1)
            self.assertTrue(all(row["group_type"] == "source" for row in payload["rows"]))
            self.assertTrue(all(row["group"] == "Source A" for row in payload["rows"]))
            self.assertEqual(payload["rows"][0]["movement_pattern_pca"], "jump-led")
        finally:
            self.current_payload_path.write_text(original_payload, encoding="utf-8")
            self.client.get("/api/news/stats?refresh=1")

    def test_export_group_temporal_popularity_momentum_accepts_tag_filters(self):
        original_payload = self.current_payload_path.read_text(encoding="utf-8")
        try:
            self.current_payload_path.write_text(json.dumps(_sparse_bucket_temporal_payload()), encoding="utf-8")
            exported = self.client.get(
                "/api/news/export?artifact=group_temporal_popularity_momentum&format=json&refresh=1&group_type=tag&group_key=risk"
            )
            self.assertEqual(exported.status_code, 200)

            payload = exported.json()
            self.assertEqual(payload["artifact"], "group_temporal_popularity_momentum")
            self.assertEqual(payload["filters"], {"group_type": "tag", "group_key": "risk"})
            self.assertEqual(len(payload["rows"]), 1)
            self.assertEqual(payload["rows"][0]["group"], "Risk")
            self.assertEqual(payload["rows"][0]["popularity_share_direction"], "flat")
            self.assertEqual(payload["rows"][0]["popularity_recent_share_direction"], "rising")
            self.assertEqual(payload["rows"][0]["popularity_momentum_label"], "rebounding to baseline")
            self.assertIn("popularity_first_share_rank_within_type", payload["rows"][0])
            self.assertIn("popularity_latest_share_rank_within_type", payload["rows"][0])
            self.assertIn("popularity_rank_change_within_type", payload["rows"][0])
            self.assertAlmostEqual(payload["rows"][0]["popularity_recent_share_delta"], 1 / 6)
            self.assertEqual(payload["rows"][0]["popularity_share_delta_rank_within_type"], 1)
            self.assertEqual(payload["rows"][0]["popularity_recent_share_delta_rank_within_type"], 1)
        finally:
            self.current_payload_path.write_text(original_payload, encoding="utf-8")
            self.client.get("/api/news/stats?refresh=1")

    def _assert_export_current_group_temporal_popularity_momentum_filter(
        self,
        *,
        group_type: str,
        group_key: str,
        expected_row_key: str,
        expected_group: str,
    ):
        original_payload = self.current_payload_path.read_text(encoding="utf-8")
        try:
            self.current_payload_path.write_text(json.dumps(_sparse_bucket_temporal_payload()), encoding="utf-8")
            exported = self.client.get(
                f"/api/news/export?artifact=group_temporal_popularity_momentum&format=json&refresh=1"
                f"&group_type={group_type}&group_key={group_key}"
            )
            self.assertEqual(exported.status_code, 200)

            payload = exported.json()
            self.assertEqual(payload["artifact"], "group_temporal_popularity_momentum")
            self.assertEqual(payload["filters"], {"group_type": group_type, "group_key": group_key})
            self.assertEqual(payload["meta"]["source_mode"], "current")
            self.assertIsNone(payload["meta"]["snapshot_date"])
            self.assertEqual(len(payload["rows"]), 1)
            self.assertEqual(payload["rows"][0]["group_type"], group_type)
            self.assertEqual(payload["rows"][0]["group_key"], expected_row_key)
            self.assertEqual(payload["rows"][0]["group"], expected_group)
            self.assertEqual(payload["rows"][0]["popularity_peak_bucket"], "2026-03-30")
            self.assertEqual(payload["rows"][0]["popularity_peak_articles"], 2)
            self.assertEqual(payload["rows"][0]["popularity_first_share"], 0.5)
            self.assertEqual(payload["rows"][0]["popularity_latest_share"], 0.5)
            self.assertEqual(payload["rows"][0]["popularity_share_delta"], 0.0)
            self.assertAlmostEqual(payload["rows"][0]["popularity_recent_share_delta"], 1 / 6)
            self.assertEqual(payload["rows"][0]["popularity_share_direction"], "flat")
            self.assertEqual(payload["rows"][0]["popularity_recent_share_direction"], "rising")
            self.assertEqual(payload["rows"][0]["popularity_momentum_label"], "rebounding to baseline")
            self.assertEqual(payload["rows"][0]["popularity_first_share_rank_within_type"], 1)
            self.assertEqual(payload["rows"][0]["popularity_latest_share_rank_within_type"], 1)
            self.assertEqual(payload["rows"][0]["popularity_rank_change_within_type"], 0)
            self.assertEqual(payload["rows"][0]["popularity_share_delta_rank_within_type"], 1)
            self.assertEqual(payload["rows"][0]["popularity_recent_share_delta_rank_within_type"], 1)
        finally:
            self.current_payload_path.write_text(original_payload, encoding="utf-8")
            self.client.get("/api/news/stats?refresh=1")

    def _assert_export_current_group_temporal_popularity_momentum_csv_filter(
        self,
        *,
        group_type: str,
        group_key: str,
        expected_row_key: str,
        expected_group: str,
    ):
        original_payload = self.current_payload_path.read_text(encoding="utf-8")
        try:
            self.current_payload_path.write_text(json.dumps(_sparse_bucket_temporal_payload()), encoding="utf-8")
            exported = self.client.get(
                f"/api/news/export?artifact=group_temporal_popularity_momentum&format=csv&refresh=1"
                f"&group_type={group_type}&group_key={group_key}"
            )
            self.assertEqual(exported.status_code, 200)
            self.assertIn("text/csv", exported.headers.get("content-type", ""))
            self.assertEqual(exported.headers.get("cache-control"), "no-store")
            self.assertIn(
                "group_temporal_popularity_momentum.csv",
                exported.headers.get("content-disposition", ""),
            )

            reader = csv.DictReader(io.StringIO(exported.text))
            self.assertIsNotNone(reader.fieldnames)
            self.assertIn("group_type", reader.fieldnames)
            self.assertIn("group_key", reader.fieldnames)
            self.assertIn("popularity_peak_bucket", reader.fieldnames)
            self.assertIn("popularity_momentum_label", reader.fieldnames)
            self.assertIn("popularity_recent_share_delta_rank_within_type", reader.fieldnames)

            rows = list(reader)
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]["group_type"], group_type)
            self.assertEqual(rows[0]["group_key"], expected_row_key)
            self.assertEqual(rows[0]["group"], expected_group)
            self.assertEqual(rows[0]["popularity_peak_bucket"], "2026-03-30")
            self.assertEqual(rows[0]["popularity_peak_articles"], "2")
            self.assertEqual(rows[0]["popularity_first_share"], "0.5")
            self.assertEqual(rows[0]["popularity_latest_share"], "0.5")
            self.assertEqual(rows[0]["popularity_share_delta"], "0.0")
            self.assertAlmostEqual(float(rows[0]["popularity_recent_share_delta"]), 1 / 6)
            self.assertEqual(rows[0]["popularity_share_direction"], "flat")
            self.assertEqual(rows[0]["popularity_recent_share_direction"], "rising")
            self.assertEqual(rows[0]["popularity_momentum_label"], "rebounding to baseline")
            self.assertEqual(rows[0]["popularity_first_share_rank_within_type"], "1")
            self.assertEqual(rows[0]["popularity_latest_share_rank_within_type"], "1")
            self.assertEqual(rows[0]["popularity_rank_change_within_type"], "0")
            self.assertEqual(rows[0]["popularity_share_delta_rank_within_type"], "1")
            self.assertEqual(rows[0]["popularity_recent_share_delta_rank_within_type"], "1")
        finally:
            self.current_payload_path.write_text(original_payload, encoding="utf-8")
            self.client.get("/api/news/stats?refresh=1")

    def _assert_export_current_group_temporal_path_summary_filter(
        self,
        *,
        group_type: str,
        group_key: str,
        expected_row_key: str,
        expected_group: str,
    ):
        original_payload = self.current_payload_path.read_text(encoding="utf-8")
        try:
            self.current_payload_path.write_text(json.dumps(_sparse_bucket_temporal_payload()), encoding="utf-8")
            exported = self.client.get(
                f"/api/news/export?artifact=group_temporal_path_summary&format=json&refresh=1"
                f"&group_type={group_type}&group_key={group_key}"
            )
            self.assertEqual(exported.status_code, 200)

            payload = exported.json()
            self.assertEqual(payload["artifact"], "group_temporal_path_summary")
            self.assertEqual(payload["filters"], {"group_type": group_type, "group_key": group_key})
            self.assertEqual(payload["meta"]["source_mode"], "current")
            self.assertIsNone(payload["meta"]["snapshot_date"])
            self.assertEqual(len(payload["rows"]), 1)
            self.assertEqual(payload["rows"][0]["group_type"], group_type)
            self.assertEqual(payload["rows"][0]["group_key"], expected_row_key)
            self.assertEqual(payload["rows"][0]["group"], expected_group)
            self.assertEqual(payload["rows"][0]["coverage_gap_count"], 1)
            self.assertEqual(payload["rows"][0]["coverage_gap_labels"], "2026-04-13")
            self.assertIn('"label": "2026-04-13"', payload["rows"][0]["coverage_gap_ranges_json"])
            self.assertEqual(payload["rows"][0]["bucket_granularity"], "week")
            self.assertEqual(payload["rows"][0]["popularity_peak_bucket"], "2026-03-30")
            self.assertEqual(payload["rows"][0]["popularity_peak_articles"], 2)
            self.assertEqual(payload["rows"][0]["popularity_first_share"], 0.5)
            self.assertEqual(payload["rows"][0]["popularity_latest_share"], 0.5)
            self.assertAlmostEqual(payload["rows"][0]["popularity_recent_share_delta"], 1 / 6)
        finally:
            self.current_payload_path.write_text(original_payload, encoding="utf-8")
            self.client.get("/api/news/stats?refresh=1")

    def _assert_export_current_group_temporal_buckets_filter(
        self,
        *,
        group_type: str,
        group_key: str,
        expected_row_key: str,
        expected_group: str,
    ):
        original_payload = self.current_payload_path.read_text(encoding="utf-8")
        try:
            self.current_payload_path.write_text(json.dumps(_sparse_bucket_temporal_payload()), encoding="utf-8")
            exported = self.client.get(
                f"/api/news/export?artifact=group_temporal_buckets&format=json&refresh=1"
                f"&group_type={group_type}&group_key={group_key}"
            )
            self.assertEqual(exported.status_code, 200)

            payload = exported.json()
            self.assertEqual(payload["artifact"], "group_temporal_buckets")
            self.assertEqual(payload["filters"], {"group_type": group_type, "group_key": group_key})
            self.assertEqual(payload["meta"]["source_mode"], "current")
            self.assertIsNone(payload["meta"]["snapshot_date"])
            self.assertEqual(len(payload["rows"]), 3)
            self.assertTrue(all(row["group_type"] == group_type for row in payload["rows"]))
            self.assertTrue(all(row["group_key"] == expected_row_key for row in payload["rows"]))
            self.assertTrue(all(row["group"] == expected_group for row in payload["rows"]))

            sparse_row = next(row for row in payload["rows"] if row["bucket_status"] == "sparse")
            self.assertEqual(sparse_row["bucket_start"], "2026-04-06")
            self.assertEqual(sparse_row["bucket_n_articles"], 1)
            self.assertEqual(sparse_row["group_sparse_bucket_count"], 1)
            self.assertEqual(sparse_row["group_coverage_gap_count"], 1)
            self.assertEqual(sparse_row["group_coverage_gap_labels"], "2026-04-13")
            self.assertIn('"label": "2026-04-13"', sparse_row["group_coverage_gap_ranges_json"])
            self.assertEqual(sparse_row["group_popularity_peak_bucket"], "2026-03-30")
            self.assertAlmostEqual(sparse_row["group_popularity_recent_share_delta"], 1 / 6)
            self.assertIn('"Source A": 1', sparse_row["bucket_source_counts_json"])
        finally:
            self.current_payload_path.write_text(original_payload, encoding="utf-8")
            self.client.get("/api/news/stats?refresh=1")

    def _assert_export_current_group_temporal_buckets_csv_filter(
        self,
        *,
        group_type: str,
        group_key: str,
        expected_row_key: str,
        expected_group: str,
    ):
        original_payload = self.current_payload_path.read_text(encoding="utf-8")
        try:
            self.current_payload_path.write_text(json.dumps(_sparse_bucket_temporal_payload()), encoding="utf-8")
            exported = self.client.get(
                f"/api/news/export?artifact=group_temporal_buckets&format=csv&refresh=1"
                f"&group_type={group_type}&group_key={group_key}"
            )
            self.assertEqual(exported.status_code, 200)
            self.assertIn("text/csv", exported.headers.get("content-type", ""))
            self.assertEqual(exported.headers.get("cache-control"), "no-store")
            self.assertIn(
                "group_temporal_buckets.csv",
                exported.headers.get("content-disposition", ""),
            )

            reader = csv.DictReader(io.StringIO(exported.text))
            self.assertIsNotNone(reader.fieldnames)
            self.assertIn("group_type", reader.fieldnames)
            self.assertIn("group_key", reader.fieldnames)
            self.assertIn("group_sparse_bucket_count", reader.fieldnames)
            self.assertIn("group_coverage_gap_labels", reader.fieldnames)
            self.assertIn("group_popularity_recent_share_delta", reader.fieldnames)
            self.assertIn("bucket_source_counts_json", reader.fieldnames)

            rows = list(reader)
            self.assertEqual(len(rows), 3)
            self.assertTrue(all(row["group_type"] == group_type for row in rows))
            self.assertTrue(all(row["group_key"] == expected_row_key for row in rows))
            self.assertTrue(all(row["group"] == expected_group for row in rows))

            sparse_row = next(row for row in rows if row["bucket_status"] == "sparse")
            self.assertEqual(sparse_row["bucket_start"], "2026-04-06")
            self.assertEqual(sparse_row["bucket_n_articles"], "1")
            self.assertEqual(sparse_row["group_sparse_bucket_count"], "1")
            self.assertEqual(sparse_row["group_coverage_gap_count"], "1")
            self.assertEqual(sparse_row["group_coverage_gap_labels"], "2026-04-13")
            self.assertIn('"label": "2026-04-13"', sparse_row["group_coverage_gap_ranges_json"])
            self.assertEqual(sparse_row["group_popularity_peak_bucket"], "2026-03-30")
            self.assertAlmostEqual(float(sparse_row["group_popularity_recent_share_delta"]), 1 / 6)
            self.assertIn('"Source A": 1', sparse_row["bucket_source_counts_json"])
        finally:
            self.current_payload_path.write_text(original_payload, encoding="utf-8")
            self.client.get("/api/news/stats?refresh=1")

    def _assert_export_current_group_temporal_path_summary_csv_filter(
        self,
        *,
        group_type: str,
        group_key: str,
        expected_row_key: str,
        expected_group: str,
    ):
        original_payload = self.current_payload_path.read_text(encoding="utf-8")
        try:
            self.current_payload_path.write_text(json.dumps(_sparse_bucket_temporal_payload()), encoding="utf-8")
            exported = self.client.get(
                f"/api/news/export?artifact=group_temporal_path_summary&format=csv&refresh=1"
                f"&group_type={group_type}&group_key={group_key}"
            )
            self.assertEqual(exported.status_code, 200)
            self.assertIn("text/csv", exported.headers.get("content-type", ""))
            self.assertEqual(exported.headers.get("cache-control"), "no-store")
            self.assertIn(
                "group_temporal_path_summary.csv",
                exported.headers.get("content-disposition", ""),
            )

            reader = csv.DictReader(io.StringIO(exported.text))
            self.assertIsNotNone(reader.fieldnames)
            self.assertIn("group_type", reader.fieldnames)
            self.assertIn("group_key", reader.fieldnames)
            self.assertIn("coverage_gap_labels", reader.fieldnames)
            self.assertIn("coverage_gap_ranges_json", reader.fieldnames)
            self.assertIn("popularity_recent_share_delta", reader.fieldnames)

            rows = list(reader)
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]["group_type"], group_type)
            self.assertEqual(rows[0]["group_key"], expected_row_key)
            self.assertEqual(rows[0]["group"], expected_group)
            self.assertEqual(rows[0]["coverage_gap_count"], "1")
            self.assertEqual(rows[0]["coverage_gap_labels"], "2026-04-13")
            self.assertIn('"label": "2026-04-13"', rows[0]["coverage_gap_ranges_json"])
            self.assertEqual(rows[0]["popularity_peak_bucket"], "2026-03-30")
            self.assertEqual(rows[0]["popularity_peak_articles"], "2")
            self.assertEqual(rows[0]["popularity_first_share"], "0.5")
            self.assertEqual(rows[0]["popularity_latest_share"], "0.5")
            self.assertAlmostEqual(float(rows[0]["popularity_recent_share_delta"]), 1 / 6)
        finally:
            self.current_payload_path.write_text(original_payload, encoding="utf-8")
            self.client.get("/api/news/stats?refresh=1")

    def test_export_current_group_temporal_popularity_momentum_keeps_source_filters(self):
        self._assert_export_current_group_temporal_popularity_momentum_filter(
            group_type="source",
            group_key="source-a",
            expected_row_key="source a",
            expected_group="Source A",
        )

    def test_export_current_group_temporal_popularity_momentum_normalizes_source_group_key_variants(self):
        self._assert_export_current_group_temporal_popularity_momentum_filter(
            group_type="source",
            group_key="Source_A",
            expected_row_key="source a",
            expected_group="Source A",
        )

    def test_export_current_group_temporal_popularity_momentum_keeps_topic_filters(self):
        self._assert_export_current_group_temporal_popularity_momentum_filter(
            group_type="topic",
            group_key="policy",
            expected_row_key="policy",
            expected_group="Policy",
        )

    def test_export_current_group_temporal_popularity_momentum_csv_keeps_group_filters(self):
        self._assert_export_current_group_temporal_popularity_momentum_csv_filter(
            group_type="tag",
            group_key="risk",
            expected_row_key="risk",
            expected_group="Risk",
        )

    def test_export_current_group_temporal_popularity_momentum_csv_keeps_source_filters(self):
        self._assert_export_current_group_temporal_popularity_momentum_csv_filter(
            group_type="source",
            group_key="source-a",
            expected_row_key="source a",
            expected_group="Source A",
        )

    def test_export_current_group_temporal_popularity_momentum_csv_normalizes_source_group_key_variants(self):
        self._assert_export_current_group_temporal_popularity_momentum_csv_filter(
            group_type="source",
            group_key="Source_A",
            expected_row_key="source a",
            expected_group="Source A",
        )

    def test_export_current_group_temporal_popularity_momentum_csv_keeps_topic_filters(self):
        self._assert_export_current_group_temporal_popularity_momentum_csv_filter(
            group_type="topic",
            group_key="policy",
            expected_row_key="policy",
            expected_group="Policy",
        )

    def test_export_current_group_temporal_path_summary_keeps_group_filters(self):
        self._assert_export_current_group_temporal_path_summary_filter(
            group_type="tag",
            group_key="risk",
            expected_row_key="risk",
            expected_group="Risk",
        )

    def test_export_current_group_temporal_path_summary_keeps_source_filters(self):
        self._assert_export_current_group_temporal_path_summary_filter(
            group_type="source",
            group_key="source-a",
            expected_row_key="source a",
            expected_group="Source A",
        )

    def test_export_current_group_temporal_path_summary_normalizes_source_group_key_variants(self):
        self._assert_export_current_group_temporal_path_summary_filter(
            group_type="source",
            group_key="Source_A",
            expected_row_key="source a",
            expected_group="Source A",
        )

    def test_export_current_group_temporal_path_summary_keeps_topic_filters(self):
        self._assert_export_current_group_temporal_path_summary_filter(
            group_type="topic",
            group_key="policy",
            expected_row_key="policy",
            expected_group="Policy",
        )

    def test_export_current_group_temporal_buckets_keeps_group_filters(self):
        self._assert_export_current_group_temporal_buckets_filter(
            group_type="tag",
            group_key="risk",
            expected_row_key="risk",
            expected_group="Risk",
        )

    def test_export_current_group_temporal_buckets_keeps_source_filters(self):
        self._assert_export_current_group_temporal_buckets_filter(
            group_type="source",
            group_key="source-a",
            expected_row_key="source a",
            expected_group="Source A",
        )

    def test_export_current_group_temporal_buckets_normalizes_source_group_key_variants(self):
        self._assert_export_current_group_temporal_buckets_filter(
            group_type="source",
            group_key="Source_A",
            expected_row_key="source a",
            expected_group="Source A",
        )

    def test_export_current_group_temporal_buckets_supports_bucket_label_filters(self):
        original_payload = self.current_payload_path.read_text(encoding="utf-8")
        try:
            self.current_payload_path.write_text(json.dumps(_sparse_bucket_temporal_payload()), encoding="utf-8")
            exported = self.client.get(
                "/api/news/export?artifact=group_temporal_buckets&format=json&refresh=1"
                "&group_type=source&group_key=Source_A&bucket_label=2026-04-06"
            )
            self.assertEqual(exported.status_code, 200)

            payload = exported.json()
            self.assertEqual(payload["artifact"], "group_temporal_buckets")
            self.assertEqual(
                payload["filters"],
                {"group_type": "source", "group_key": "Source_A", "bucket_label": "2026-04-06"},
            )
            self.assertEqual(payload["meta"]["source_mode"], "current")
            self.assertIsNone(payload["meta"]["snapshot_date"])
            self.assertEqual(len(payload["rows"]), 1)
            self.assertEqual(payload["rows"][0]["group_type"], "source")
            self.assertEqual(payload["rows"][0]["group_key"], "source a")
            self.assertEqual(payload["rows"][0]["group"], "Source A")
            self.assertEqual(payload["rows"][0]["bucket_label"], "2026-04-06")
            self.assertEqual(payload["rows"][0]["bucket_status"], "sparse")
            self.assertEqual(payload["rows"][0]["bucket_n_articles"], 1)
        finally:
            self.current_payload_path.write_text(original_payload, encoding="utf-8")
            self.client.get("/api/news/stats?refresh=1")

    def test_export_current_group_temporal_buckets_supports_bucket_label_filters_without_group_key(self):
        original_payload = self.current_payload_path.read_text(encoding="utf-8")
        try:
            self.current_payload_path.write_text(json.dumps(_sparse_bucket_temporal_payload()), encoding="utf-8")
            exported = self.client.get(
                "/api/news/export?artifact=group_temporal_buckets&format=json&refresh=1"
                "&bucket_label=2026-04-06"
            )
            self.assertEqual(exported.status_code, 200)

            payload = exported.json()
            self.assertEqual(payload["artifact"], "group_temporal_buckets")
            self.assertEqual(payload["filters"], {"bucket_label": "2026-04-06"})
            self.assertEqual(payload["meta"]["source_mode"], "current")
            self.assertIsNone(payload["meta"]["snapshot_date"])
            self.assertEqual(len(payload["rows"]), 6)
            self.assertEqual({row["group_type"] for row in payload["rows"]}, {"source", "topic", "tag"})
            self.assertEqual({row["group_key"] for row in payload["rows"]}, {"source a", "source b", "policy", "markets", "risk", "growth"})
            self.assertTrue(all(row["bucket_label"] == "2026-04-06" for row in payload["rows"]))
            self.assertEqual(sum(1 for row in payload["rows"] if row["bucket_status"] == "sparse"), 3)
        finally:
            self.current_payload_path.write_text(original_payload, encoding="utf-8")
            self.client.get("/api/news/stats?refresh=1")

    def test_export_current_group_temporal_buckets_csv_supports_bucket_label_filters_without_group_key(self):
        original_payload = self.current_payload_path.read_text(encoding="utf-8")
        try:
            self.current_payload_path.write_text(json.dumps(_sparse_bucket_temporal_payload()), encoding="utf-8")
            exported = self.client.get(
                "/api/news/export?artifact=group_temporal_buckets&format=csv&refresh=1"
                "&bucket_label=2026-04-06"
            )
            self.assertEqual(exported.status_code, 200)
            self.assertIn("text/csv", exported.headers.get("content-type", ""))
            self.assertEqual(exported.headers.get("cache-control"), "no-store")

            rows = list(csv.DictReader(io.StringIO(exported.text)))
            self.assertEqual(len(rows), 6)
            self.assertEqual({row["group_type"] for row in rows}, {"source", "topic", "tag"})
            self.assertEqual(
                {row["group_key"] for row in rows},
                {"source a", "source b", "policy", "markets", "risk", "growth"},
            )
            self.assertTrue(all(row["bucket_label"] == "2026-04-06" for row in rows))
            self.assertEqual(sum(1 for row in rows if row["bucket_status"] == "sparse"), 3)
        finally:
            self.current_payload_path.write_text(original_payload, encoding="utf-8")
            self.client.get("/api/news/stats?refresh=1")

    def test_export_current_group_temporal_buckets_supports_bucket_label_filters_for_multi_word_topic_keys(self):
        original_payload = self.current_payload_path.read_text(encoding="utf-8")
        try:
            self.current_payload_path.write_text(
                json.dumps(_sparse_bucket_temporal_payload_with_multi_word_topic()),
                encoding="utf-8",
            )
            exported = self.client.get(
                "/api/news/export?artifact=group_temporal_buckets&format=json&refresh=1"
                "&group_type=topic&group_key=Climate_Risk&bucket_label=2026-03-30"
            )
            self.assertEqual(exported.status_code, 200)

            payload = exported.json()
            self.assertEqual(payload["artifact"], "group_temporal_buckets")
            self.assertEqual(
                payload["filters"],
                {"group_type": "topic", "group_key": "Climate_Risk", "bucket_label": "2026-03-30"},
            )
            self.assertEqual(payload["meta"]["source_mode"], "current")
            self.assertIsNone(payload["meta"]["snapshot_date"])
            self.assertEqual(len(payload["rows"]), 1)
            self.assertEqual(payload["rows"][0]["group_type"], "topic")
            self.assertEqual(payload["rows"][0]["group_key"], "climate risk")
            self.assertEqual(payload["rows"][0]["group"], "Climate Risk")
            self.assertEqual(payload["rows"][0]["bucket_label"], "2026-03-30")
            self.assertEqual(payload["rows"][0]["bucket_status"], "ok")
            self.assertEqual(payload["rows"][0]["bucket_n_articles"], 2)
        finally:
            self.current_payload_path.write_text(original_payload, encoding="utf-8")
            self.client.get("/api/news/stats?refresh=1")

    def test_export_current_group_temporal_buckets_csv_supports_bucket_label_filters_for_multi_word_topic_keys(self):
        original_payload = self.current_payload_path.read_text(encoding="utf-8")
        try:
            self.current_payload_path.write_text(
                json.dumps(_sparse_bucket_temporal_payload_with_multi_word_topic()),
                encoding="utf-8",
            )
            exported = self.client.get(
                "/api/news/export?artifact=group_temporal_buckets&format=csv&refresh=1"
                "&group_type=topic&group_key=Climate_Risk&bucket_label=2026-03-30"
            )
            self.assertEqual(exported.status_code, 200)
            self.assertIn("text/csv", exported.headers.get("content-type", ""))
            self.assertEqual(exported.headers.get("cache-control"), "no-store")

            rows = list(csv.DictReader(io.StringIO(exported.text)))
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]["group_type"], "topic")
            self.assertEqual(rows[0]["group_key"], "climate risk")
            self.assertEqual(rows[0]["group"], "Climate Risk")
            self.assertEqual(rows[0]["bucket_label"], "2026-03-30")
            self.assertEqual(rows[0]["bucket_status"], "ok")
            self.assertEqual(rows[0]["bucket_n_articles"], "2")
        finally:
            self.current_payload_path.write_text(original_payload, encoding="utf-8")
            self.client.get("/api/news/stats?refresh=1")

    def test_export_current_group_temporal_buckets_keeps_topic_filters(self):
        self._assert_export_current_group_temporal_buckets_filter(
            group_type="topic",
            group_key="policy",
            expected_row_key="policy",
            expected_group="Policy",
        )

    def test_export_current_group_temporal_buckets_csv_keeps_group_filters(self):
        self._assert_export_current_group_temporal_buckets_csv_filter(
            group_type="tag",
            group_key="risk",
            expected_row_key="risk",
            expected_group="Risk",
        )

    def test_export_current_group_temporal_buckets_csv_keeps_source_filters(self):
        self._assert_export_current_group_temporal_buckets_csv_filter(
            group_type="source",
            group_key="source-a",
            expected_row_key="source a",
            expected_group="Source A",
        )

    def test_export_current_group_temporal_buckets_csv_normalizes_source_group_key_variants(self):
        self._assert_export_current_group_temporal_buckets_csv_filter(
            group_type="source",
            group_key="Source_A",
            expected_row_key="source a",
            expected_group="Source A",
        )

    def test_export_current_group_temporal_buckets_csv_keeps_topic_filters(self):
        self._assert_export_current_group_temporal_buckets_csv_filter(
            group_type="topic",
            group_key="policy",
            expected_row_key="policy",
            expected_group="Policy",
        )

    def test_export_current_group_temporal_path_summary_csv_keeps_group_filters(self):
        self._assert_export_current_group_temporal_path_summary_csv_filter(
            group_type="tag",
            group_key="risk",
            expected_row_key="risk",
            expected_group="Risk",
        )

    def test_export_current_group_temporal_path_summary_csv_keeps_source_filters(self):
        self._assert_export_current_group_temporal_path_summary_csv_filter(
            group_type="source",
            group_key="source-a",
            expected_row_key="source a",
            expected_group="Source A",
        )

    def test_export_current_group_temporal_path_summary_csv_normalizes_source_group_key_variants(self):
        self._assert_export_current_group_temporal_path_summary_csv_filter(
            group_type="source",
            group_key="Source_A",
            expected_row_key="source a",
            expected_group="Source A",
        )

    def test_export_current_group_temporal_path_summary_csv_keeps_topic_filters(self):
        self._assert_export_current_group_temporal_path_summary_csv_filter(
            group_type="topic",
            group_key="policy",
            expected_row_key="policy",
            expected_group="Policy",
        )

    def test_export_snapshot_group_temporal_popularity_momentum_keeps_group_filters(self):
        original_payload = self.snapshot_payload_path.read_text(encoding="utf-8")
        try:
            self.snapshot_payload_path.write_text(json.dumps(_sparse_bucket_temporal_payload()), encoding="utf-8")
            exported = self.client.get(
                f"/api/news/export?artifact=group_temporal_popularity_momentum&format=json&refresh=1"
                f"&group_type=tag&group_key=risk&snapshot_date={self.snapshot_date}"
            )
            self.assertEqual(exported.status_code, 200)

            payload = exported.json()
            self.assertEqual(payload["artifact"], "group_temporal_popularity_momentum")
            self.assertEqual(payload["filters"], {"group_type": "tag", "group_key": "risk"})
            self.assertEqual(payload["meta"]["source_mode"], "snapshot")
            self.assertEqual(payload["meta"]["snapshot_date"], self.snapshot_date)
            self.assertEqual(len(payload["rows"]), 1)
            self.assertEqual(payload["rows"][0]["group"], "Risk")
            self.assertEqual(payload["rows"][0]["popularity_momentum_label"], "rebounding to baseline")
            self.assertAlmostEqual(payload["rows"][0]["popularity_recent_share_delta"], 1 / 6)
        finally:
            self.snapshot_payload_path.write_text(original_payload, encoding="utf-8")
            self.client.get(f"/api/news/stats?refresh=1&snapshot_date={self.snapshot_date}")

    def test_export_snapshot_group_temporal_popularity_momentum_keeps_source_filters(self):
        original_payload = self.snapshot_payload_path.read_text(encoding="utf-8")
        try:
            self.snapshot_payload_path.write_text(json.dumps(_sparse_bucket_temporal_payload()), encoding="utf-8")
            exported = self.client.get(
                f"/api/news/export?artifact=group_temporal_popularity_momentum&format=json&refresh=1"
                f"&group_type=source&group_key=source-a&snapshot_date={self.snapshot_date}"
            )
            self.assertEqual(exported.status_code, 200)

            payload = exported.json()
            self.assertEqual(payload["artifact"], "group_temporal_popularity_momentum")
            self.assertEqual(payload["filters"], {"group_type": "source", "group_key": "source-a"})
            self.assertEqual(payload["meta"]["source_mode"], "snapshot")
            self.assertEqual(payload["meta"]["snapshot_date"], self.snapshot_date)
            self.assertEqual(len(payload["rows"]), 1)
            self.assertEqual(payload["rows"][0]["group_type"], "source")
            self.assertEqual(payload["rows"][0]["group_key"], "source a")
            self.assertEqual(payload["rows"][0]["group"], "Source A")
            self.assertEqual(payload["rows"][0]["popularity_peak_bucket"], "2026-03-30")
            self.assertEqual(payload["rows"][0]["popularity_peak_articles"], 2)
            self.assertEqual(payload["rows"][0]["popularity_first_share"], 0.5)
            self.assertEqual(payload["rows"][0]["popularity_latest_share"], 0.5)
            self.assertEqual(payload["rows"][0]["popularity_share_delta"], 0.0)
            self.assertAlmostEqual(payload["rows"][0]["popularity_recent_share_delta"], 1 / 6)
            self.assertEqual(payload["rows"][0]["popularity_momentum_label"], "rebounding to baseline")
            self.assertEqual(payload["rows"][0]["popularity_share_delta_rank_within_type"], 1)
            self.assertEqual(payload["rows"][0]["popularity_recent_share_delta_rank_within_type"], 1)
        finally:
            self.snapshot_payload_path.write_text(original_payload, encoding="utf-8")
            self.client.get(f"/api/news/stats?refresh=1&snapshot_date={self.snapshot_date}")

    def test_export_snapshot_group_temporal_popularity_momentum_normalizes_source_group_key_variants(self):
        original_payload = self.snapshot_payload_path.read_text(encoding="utf-8")
        try:
            self.snapshot_payload_path.write_text(json.dumps(_sparse_bucket_temporal_payload()), encoding="utf-8")
            exported = self.client.get(
                f"/api/news/export?artifact=group_temporal_popularity_momentum&format=json&refresh=1"
                f"&group_type=source&group_key=Source_A&snapshot_date={self.snapshot_date}"
            )
            self.assertEqual(exported.status_code, 200)

            payload = exported.json()
            self.assertEqual(payload["artifact"], "group_temporal_popularity_momentum")
            self.assertEqual(payload["filters"], {"group_type": "source", "group_key": "Source_A"})
            self.assertEqual(payload["meta"]["source_mode"], "snapshot")
            self.assertEqual(payload["meta"]["snapshot_date"], self.snapshot_date)
            self.assertEqual(len(payload["rows"]), 1)
            self.assertEqual(payload["rows"][0]["group_type"], "source")
            self.assertEqual(payload["rows"][0]["group_key"], "source a")
            self.assertEqual(payload["rows"][0]["group"], "Source A")
            self.assertEqual(payload["rows"][0]["popularity_peak_bucket"], "2026-03-30")
            self.assertEqual(payload["rows"][0]["popularity_peak_articles"], 2)
            self.assertEqual(payload["rows"][0]["popularity_first_share"], 0.5)
            self.assertEqual(payload["rows"][0]["popularity_latest_share"], 0.5)
            self.assertEqual(payload["rows"][0]["popularity_share_delta"], 0.0)
            self.assertAlmostEqual(payload["rows"][0]["popularity_recent_share_delta"], 1 / 6)
            self.assertEqual(payload["rows"][0]["popularity_momentum_label"], "rebounding to baseline")
            self.assertEqual(payload["rows"][0]["popularity_share_delta_rank_within_type"], 1)
            self.assertEqual(payload["rows"][0]["popularity_recent_share_delta_rank_within_type"], 1)
        finally:
            self.snapshot_payload_path.write_text(original_payload, encoding="utf-8")
            self.client.get(f"/api/news/stats?refresh=1&snapshot_date={self.snapshot_date}")

    def test_export_snapshot_group_temporal_popularity_momentum_keeps_topic_filters(self):
        original_payload = self.snapshot_payload_path.read_text(encoding="utf-8")
        try:
            self.snapshot_payload_path.write_text(json.dumps(_sparse_bucket_temporal_payload()), encoding="utf-8")
            exported = self.client.get(
                f"/api/news/export?artifact=group_temporal_popularity_momentum&format=json&refresh=1"
                f"&group_type=topic&group_key=policy&snapshot_date={self.snapshot_date}"
            )
            self.assertEqual(exported.status_code, 200)

            payload = exported.json()
            self.assertEqual(payload["artifact"], "group_temporal_popularity_momentum")
            self.assertEqual(payload["filters"], {"group_type": "topic", "group_key": "policy"})
            self.assertEqual(payload["meta"]["source_mode"], "snapshot")
            self.assertEqual(payload["meta"]["snapshot_date"], self.snapshot_date)
            self.assertEqual(len(payload["rows"]), 1)
            self.assertEqual(payload["rows"][0]["group_type"], "topic")
            self.assertEqual(payload["rows"][0]["group_key"], "policy")
            self.assertEqual(payload["rows"][0]["group"], "Policy")
            self.assertEqual(payload["rows"][0]["popularity_peak_bucket"], "2026-03-30")
            self.assertEqual(payload["rows"][0]["popularity_peak_articles"], 2)
            self.assertEqual(payload["rows"][0]["popularity_first_share"], 0.5)
            self.assertEqual(payload["rows"][0]["popularity_latest_share"], 0.5)
            self.assertEqual(payload["rows"][0]["popularity_share_delta"], 0.0)
            self.assertAlmostEqual(payload["rows"][0]["popularity_recent_share_delta"], 1 / 6)
            self.assertEqual(payload["rows"][0]["popularity_momentum_label"], "rebounding to baseline")
            self.assertEqual(payload["rows"][0]["popularity_share_delta_rank_within_type"], 1)
            self.assertEqual(payload["rows"][0]["popularity_recent_share_delta_rank_within_type"], 1)
        finally:
            self.snapshot_payload_path.write_text(original_payload, encoding="utf-8")
            self.client.get(f"/api/news/stats?refresh=1&snapshot_date={self.snapshot_date}")

    def test_export_snapshot_group_temporal_popularity_momentum_csv_keeps_group_filters(self):
        original_payload = self.snapshot_payload_path.read_text(encoding="utf-8")
        try:
            self.snapshot_payload_path.write_text(json.dumps(_sparse_bucket_temporal_payload()), encoding="utf-8")
            exported = self.client.get(
                f"/api/news/export?artifact=group_temporal_popularity_momentum&format=csv&refresh=1"
                f"&group_type=tag&group_key=risk&snapshot_date={self.snapshot_date}"
            )
            self.assertEqual(exported.status_code, 200)
            self.assertIn("text/csv", exported.headers.get("content-type", ""))
            self.assertEqual(exported.headers.get("cache-control"), "no-store")
            self.assertIn(
                "group_temporal_popularity_momentum.csv",
                exported.headers.get("content-disposition", ""),
            )

            reader = csv.DictReader(io.StringIO(exported.text))
            self.assertIsNotNone(reader.fieldnames)
            self.assertIn("group_type", reader.fieldnames)
            self.assertIn("group_key", reader.fieldnames)
            self.assertIn("popularity_momentum_label", reader.fieldnames)
            self.assertIn("popularity_share_delta_rank_within_type", reader.fieldnames)
            self.assertIn("popularity_recent_share_delta_rank_within_type", reader.fieldnames)

            rows = list(reader)
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]["group_type"], "tag")
            self.assertEqual(rows[0]["group_key"], "risk")
            self.assertEqual(rows[0]["group"], "Risk")
            self.assertEqual(rows[0]["popularity_momentum_label"], "rebounding to baseline")
            self.assertEqual(rows[0]["popularity_share_delta"], "0.0")
            self.assertAlmostEqual(float(rows[0]["popularity_recent_share_delta"]), 1 / 6)
            self.assertEqual(rows[0]["popularity_share_delta_rank_within_type"], "1")
            self.assertEqual(rows[0]["popularity_recent_share_delta_rank_within_type"], "1")
        finally:
            self.snapshot_payload_path.write_text(original_payload, encoding="utf-8")
            self.client.get(f"/api/news/stats?refresh=1&snapshot_date={self.snapshot_date}")

    def test_export_snapshot_group_temporal_popularity_momentum_csv_keeps_source_filters(self):
        original_payload = self.snapshot_payload_path.read_text(encoding="utf-8")
        try:
            self.snapshot_payload_path.write_text(json.dumps(_sparse_bucket_temporal_payload()), encoding="utf-8")
            exported = self.client.get(
                f"/api/news/export?artifact=group_temporal_popularity_momentum&format=csv&refresh=1"
                f"&group_type=source&group_key=source-a&snapshot_date={self.snapshot_date}"
            )
            self.assertEqual(exported.status_code, 200)
            self.assertIn("text/csv", exported.headers.get("content-type", ""))
            self.assertEqual(exported.headers.get("cache-control"), "no-store")
            self.assertIn(
                "group_temporal_popularity_momentum.csv",
                exported.headers.get("content-disposition", ""),
            )

            reader = csv.DictReader(io.StringIO(exported.text))
            self.assertIsNotNone(reader.fieldnames)
            self.assertIn("group_type", reader.fieldnames)
            self.assertIn("group_key", reader.fieldnames)
            self.assertIn("popularity_peak_bucket", reader.fieldnames)
            self.assertIn("popularity_momentum_label", reader.fieldnames)
            self.assertIn("popularity_recent_share_delta_rank_within_type", reader.fieldnames)

            rows = list(reader)
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]["group_type"], "source")
            self.assertEqual(rows[0]["group_key"], "source a")
            self.assertEqual(rows[0]["group"], "Source A")
            self.assertEqual(rows[0]["popularity_peak_bucket"], "2026-03-30")
            self.assertEqual(rows[0]["popularity_peak_articles"], "2")
            self.assertEqual(rows[0]["popularity_first_share"], "0.5")
            self.assertEqual(rows[0]["popularity_latest_share"], "0.5")
            self.assertEqual(rows[0]["popularity_share_delta"], "0.0")
            self.assertAlmostEqual(float(rows[0]["popularity_recent_share_delta"]), 1 / 6)
            self.assertEqual(rows[0]["popularity_momentum_label"], "rebounding to baseline")
            self.assertEqual(rows[0]["popularity_share_delta_rank_within_type"], "1")
            self.assertEqual(rows[0]["popularity_recent_share_delta_rank_within_type"], "1")
        finally:
            self.snapshot_payload_path.write_text(original_payload, encoding="utf-8")
            self.client.get(f"/api/news/stats?refresh=1&snapshot_date={self.snapshot_date}")

    def test_export_snapshot_group_temporal_popularity_momentum_csv_normalizes_source_group_key_variants(self):
        original_payload = self.snapshot_payload_path.read_text(encoding="utf-8")
        try:
            self.snapshot_payload_path.write_text(json.dumps(_sparse_bucket_temporal_payload()), encoding="utf-8")
            exported = self.client.get(
                f"/api/news/export?artifact=group_temporal_popularity_momentum&format=csv&refresh=1"
                f"&group_type=source&group_key=Source_A&snapshot_date={self.snapshot_date}"
            )
            self.assertEqual(exported.status_code, 200)
            self.assertIn("text/csv", exported.headers.get("content-type", ""))
            self.assertEqual(exported.headers.get("cache-control"), "no-store")
            self.assertIn(
                "group_temporal_popularity_momentum.csv",
                exported.headers.get("content-disposition", ""),
            )

            reader = csv.DictReader(io.StringIO(exported.text))
            self.assertIsNotNone(reader.fieldnames)
            self.assertIn("group_type", reader.fieldnames)
            self.assertIn("group_key", reader.fieldnames)
            self.assertIn("popularity_peak_bucket", reader.fieldnames)
            self.assertIn("popularity_momentum_label", reader.fieldnames)
            self.assertIn("popularity_recent_share_delta_rank_within_type", reader.fieldnames)

            rows = list(reader)
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]["group_type"], "source")
            self.assertEqual(rows[0]["group_key"], "source a")
            self.assertEqual(rows[0]["group"], "Source A")
            self.assertEqual(rows[0]["popularity_peak_bucket"], "2026-03-30")
            self.assertEqual(rows[0]["popularity_peak_articles"], "2")
            self.assertEqual(rows[0]["popularity_first_share"], "0.5")
            self.assertEqual(rows[0]["popularity_latest_share"], "0.5")
            self.assertEqual(rows[0]["popularity_share_delta"], "0.0")
            self.assertAlmostEqual(float(rows[0]["popularity_recent_share_delta"]), 1 / 6)
            self.assertEqual(rows[0]["popularity_momentum_label"], "rebounding to baseline")
            self.assertEqual(rows[0]["popularity_share_delta_rank_within_type"], "1")
            self.assertEqual(rows[0]["popularity_recent_share_delta_rank_within_type"], "1")
        finally:
            self.snapshot_payload_path.write_text(original_payload, encoding="utf-8")
            self.client.get(f"/api/news/stats?refresh=1&snapshot_date={self.snapshot_date}")
    def test_export_snapshot_group_temporal_popularity_momentum_csv_keeps_topic_filters(self):
        original_payload = self.snapshot_payload_path.read_text(encoding="utf-8")
        try:
            self.snapshot_payload_path.write_text(json.dumps(_sparse_bucket_temporal_payload()), encoding="utf-8")
            exported = self.client.get(
                f"/api/news/export?artifact=group_temporal_popularity_momentum&format=csv&refresh=1"
                f"&group_type=topic&group_key=policy&snapshot_date={self.snapshot_date}"
            )
            self.assertEqual(exported.status_code, 200)
            self.assertIn("text/csv", exported.headers.get("content-type", ""))
            self.assertEqual(exported.headers.get("cache-control"), "no-store")
            self.assertIn(
                "group_temporal_popularity_momentum.csv",
                exported.headers.get("content-disposition", ""),
            )

            reader = csv.DictReader(io.StringIO(exported.text))
            self.assertIsNotNone(reader.fieldnames)
            self.assertIn("group_type", reader.fieldnames)
            self.assertIn("group_key", reader.fieldnames)
            self.assertIn("popularity_peak_bucket", reader.fieldnames)
            self.assertIn("popularity_momentum_label", reader.fieldnames)
            self.assertIn("popularity_recent_share_delta_rank_within_type", reader.fieldnames)

            rows = list(reader)
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]["group_type"], "topic")
            self.assertEqual(rows[0]["group_key"], "policy")
            self.assertEqual(rows[0]["group"], "Policy")
            self.assertEqual(rows[0]["popularity_peak_bucket"], "2026-03-30")
            self.assertEqual(rows[0]["popularity_peak_articles"], "2")
            self.assertEqual(rows[0]["popularity_first_share"], "0.5")
            self.assertEqual(rows[0]["popularity_latest_share"], "0.5")
            self.assertEqual(rows[0]["popularity_share_delta"], "0.0")
            self.assertAlmostEqual(float(rows[0]["popularity_recent_share_delta"]), 1 / 6)
            self.assertEqual(rows[0]["popularity_momentum_label"], "rebounding to baseline")
            self.assertEqual(rows[0]["popularity_share_delta_rank_within_type"], "1")
            self.assertEqual(rows[0]["popularity_recent_share_delta_rank_within_type"], "1")
        finally:
            self.snapshot_payload_path.write_text(original_payload, encoding="utf-8")
            self.client.get(f"/api/news/stats?refresh=1&snapshot_date={self.snapshot_date}")

    def test_export_snapshot_group_temporal_path_summary_keeps_group_filters(self):
        original_payload = self.snapshot_payload_path.read_text(encoding="utf-8")
        try:
            self.snapshot_payload_path.write_text(json.dumps(_sparse_bucket_temporal_payload()), encoding="utf-8")
            exported = self.client.get(
                f"/api/news/export?artifact=group_temporal_path_summary&format=json&refresh=1"
                f"&group_type=tag&group_key=risk&snapshot_date={self.snapshot_date}"
            )
            self.assertEqual(exported.status_code, 200)

            payload = exported.json()
            self.assertEqual(payload["artifact"], "group_temporal_path_summary")
            self.assertEqual(payload["filters"], {"group_type": "tag", "group_key": "risk"})
            self.assertEqual(payload["meta"]["source_mode"], "snapshot")
            self.assertEqual(payload["meta"]["snapshot_date"], self.snapshot_date)
            self.assertEqual(len(payload["rows"]), 1)
            self.assertEqual(payload["rows"][0]["group"], "Risk")
            self.assertEqual(payload["rows"][0]["coverage_gap_count"], 1)
            self.assertEqual(payload["rows"][0]["coverage_gap_labels"], "2026-04-13")
            self.assertIn('"label": "2026-04-13"', payload["rows"][0]["coverage_gap_ranges_json"])
            self.assertEqual(payload["rows"][0]["popularity_peak_bucket"], "2026-03-30")
            self.assertAlmostEqual(payload["rows"][0]["popularity_recent_share_delta"], 1 / 6)
        finally:
            self.snapshot_payload_path.write_text(original_payload, encoding="utf-8")
            self.client.get(f"/api/news/stats?refresh=1&snapshot_date={self.snapshot_date}")

    def _assert_export_snapshot_group_temporal_path_summary_filter(
        self,
        *,
        group_type: str,
        group_key: str,
        expected_row_key: str,
        expected_group: str,
    ):
        original_payload = self.snapshot_payload_path.read_text(encoding="utf-8")
        try:
            self.snapshot_payload_path.write_text(json.dumps(_sparse_bucket_temporal_payload()), encoding="utf-8")
            exported = self.client.get(
                f"/api/news/export?artifact=group_temporal_path_summary&format=json&refresh=1"
                f"&group_type={group_type}&group_key={group_key}&snapshot_date={self.snapshot_date}"
            )
            self.assertEqual(exported.status_code, 200)

            payload = exported.json()
            self.assertEqual(payload["artifact"], "group_temporal_path_summary")
            self.assertEqual(payload["filters"], {"group_type": group_type, "group_key": group_key})
            self.assertEqual(payload["meta"]["source_mode"], "snapshot")
            self.assertEqual(payload["meta"]["snapshot_date"], self.snapshot_date)
            self.assertEqual(len(payload["rows"]), 1)
            self.assertEqual(payload["rows"][0]["group_type"], group_type)
            self.assertEqual(payload["rows"][0]["group_key"], expected_row_key)
            self.assertEqual(payload["rows"][0]["group"], expected_group)
            self.assertEqual(payload["rows"][0]["coverage_gap_count"], 1)
            self.assertEqual(payload["rows"][0]["coverage_gap_labels"], "2026-04-13")
            self.assertIn('"label": "2026-04-13"', payload["rows"][0]["coverage_gap_ranges_json"])
            self.assertEqual(payload["rows"][0]["bucket_granularity"], "week")
            self.assertEqual(payload["rows"][0]["popularity_peak_bucket"], "2026-03-30")
            self.assertEqual(payload["rows"][0]["popularity_peak_articles"], 2)
            self.assertEqual(payload["rows"][0]["popularity_first_share"], 0.5)
            self.assertEqual(payload["rows"][0]["popularity_latest_share"], 0.5)
            self.assertAlmostEqual(payload["rows"][0]["popularity_recent_share_delta"], 1 / 6)
        finally:
            self.snapshot_payload_path.write_text(original_payload, encoding="utf-8")
            self.client.get(f"/api/news/stats?refresh=1&snapshot_date={self.snapshot_date}")

    def test_export_snapshot_group_temporal_path_summary_keeps_source_filters(self):
        self._assert_export_snapshot_group_temporal_path_summary_filter(
            group_type="source",
            group_key="source-a",
            expected_row_key="source a",
            expected_group="Source A",
        )

    def test_export_snapshot_group_temporal_path_summary_normalizes_source_group_key_variants(self):
        self._assert_export_snapshot_group_temporal_path_summary_filter(
            group_type="source",
            group_key="Source_A",
            expected_row_key="source a",
            expected_group="Source A",
        )

    def test_export_snapshot_group_temporal_path_summary_keeps_topic_filters(self):
        self._assert_export_snapshot_group_temporal_path_summary_filter(
            group_type="topic",
            group_key="policy",
            expected_row_key="policy",
            expected_group="Policy",
        )

    def test_export_snapshot_group_temporal_buckets_keeps_group_filters(self):
        original_payload = self.snapshot_payload_path.read_text(encoding="utf-8")
        try:
            self.snapshot_payload_path.write_text(json.dumps(_sparse_bucket_temporal_payload()), encoding="utf-8")
            exported = self.client.get(
                f"/api/news/export?artifact=group_temporal_buckets&format=json&refresh=1"
                f"&group_type=tag&group_key=risk&snapshot_date={self.snapshot_date}"
            )
            self.assertEqual(exported.status_code, 200)

            payload = exported.json()
            self.assertEqual(payload["artifact"], "group_temporal_buckets")
            self.assertEqual(payload["filters"], {"group_type": "tag", "group_key": "risk"})
            self.assertEqual(payload["meta"]["source_mode"], "snapshot")
            self.assertEqual(payload["meta"]["snapshot_date"], self.snapshot_date)
            self.assertEqual(len(payload["rows"]), 3)
            self.assertTrue(all(row["group"] == "Risk" for row in payload["rows"]))

            sparse_row = next(row for row in payload["rows"] if row["bucket_status"] == "sparse")
            self.assertEqual(sparse_row["bucket_start"], "2026-04-06")
            self.assertEqual(sparse_row["bucket_n_articles"], 1)
            self.assertEqual(sparse_row["group_sparse_bucket_count"], 1)
            self.assertEqual(sparse_row["group_coverage_gap_count"], 1)
            self.assertEqual(sparse_row["group_coverage_gap_labels"], "2026-04-13")
            self.assertIn('"label": "2026-04-13"', sparse_row["group_coverage_gap_ranges_json"])
            self.assertEqual(sparse_row["group_popularity_peak_bucket"], "2026-03-30")
            self.assertAlmostEqual(sparse_row["group_popularity_recent_share_delta"], 1 / 6)
            self.assertIn('"Source A": 1', sparse_row["bucket_source_counts_json"])
        finally:
            self.snapshot_payload_path.write_text(original_payload, encoding="utf-8")
            self.client.get(f"/api/news/stats?refresh=1&snapshot_date={self.snapshot_date}")

    def _assert_export_snapshot_group_temporal_buckets_filter(
        self,
        *,
        group_type: str,
        group_key: str,
        expected_row_key: str,
        expected_group: str,
    ):
        original_payload = self.snapshot_payload_path.read_text(encoding="utf-8")
        try:
            self.snapshot_payload_path.write_text(json.dumps(_sparse_bucket_temporal_payload()), encoding="utf-8")
            exported = self.client.get(
                f"/api/news/export?artifact=group_temporal_buckets&format=json&refresh=1"
                f"&group_type={group_type}&group_key={group_key}&snapshot_date={self.snapshot_date}"
            )
            self.assertEqual(exported.status_code, 200)

            payload = exported.json()
            self.assertEqual(payload["artifact"], "group_temporal_buckets")
            self.assertEqual(payload["filters"], {"group_type": group_type, "group_key": group_key})
            self.assertEqual(payload["meta"]["source_mode"], "snapshot")
            self.assertEqual(payload["meta"]["snapshot_date"], self.snapshot_date)
            self.assertEqual(len(payload["rows"]), 3)
            self.assertTrue(all(row["group_type"] == group_type for row in payload["rows"]))
            self.assertTrue(all(row["group_key"] == expected_row_key for row in payload["rows"]))
            self.assertTrue(all(row["group"] == expected_group for row in payload["rows"]))

            sparse_row = next(row for row in payload["rows"] if row["bucket_status"] == "sparse")
            self.assertEqual(sparse_row["bucket_start"], "2026-04-06")
            self.assertEqual(sparse_row["bucket_n_articles"], 1)
            self.assertEqual(sparse_row["group_sparse_bucket_count"], 1)
            self.assertEqual(sparse_row["group_coverage_gap_count"], 1)
            self.assertEqual(sparse_row["group_coverage_gap_labels"], "2026-04-13")
            self.assertIn('"label": "2026-04-13"', sparse_row["group_coverage_gap_ranges_json"])
            self.assertEqual(sparse_row["group_popularity_peak_bucket"], "2026-03-30")
            self.assertAlmostEqual(sparse_row["group_popularity_recent_share_delta"], 1 / 6)
            self.assertIn('"Source A": 1', sparse_row["bucket_source_counts_json"])
        finally:
            self.snapshot_payload_path.write_text(original_payload, encoding="utf-8")
            self.client.get(f"/api/news/stats?refresh=1&snapshot_date={self.snapshot_date}")

    def test_export_snapshot_group_temporal_buckets_keeps_source_filters(self):
        self._assert_export_snapshot_group_temporal_buckets_filter(
            group_type="source",
            group_key="source-a",
            expected_row_key="source a",
            expected_group="Source A",
        )

    def test_export_snapshot_group_temporal_buckets_normalizes_source_group_key_variants(self):
        self._assert_export_snapshot_group_temporal_buckets_filter(
            group_type="source",
            group_key="Source_A",
            expected_row_key="source a",
            expected_group="Source A",
        )

    def test_export_snapshot_group_temporal_buckets_keeps_topic_filters(self):
        self._assert_export_snapshot_group_temporal_buckets_filter(
            group_type="topic",
            group_key="policy",
            expected_row_key="policy",
            expected_group="Policy",
        )

    def test_export_snapshot_group_temporal_buckets_supports_bucket_label_filters_for_multi_word_topic_keys(self):
        original_payload = self.snapshot_payload_path.read_text(encoding="utf-8")
        try:
            self.snapshot_payload_path.write_text(
                json.dumps(_sparse_bucket_temporal_payload_with_multi_word_topic()),
                encoding="utf-8",
            )
            exported = self.client.get(
                f"/api/news/export?artifact=group_temporal_buckets&format=json&refresh=1"
                f"&group_type=topic&group_key=Climate_Risk&bucket_label=2026-03-30&snapshot_date={self.snapshot_date}"
            )
            self.assertEqual(exported.status_code, 200)

            payload = exported.json()
            self.assertEqual(payload["artifact"], "group_temporal_buckets")
            self.assertEqual(
                payload["filters"],
                {"group_type": "topic", "group_key": "Climate_Risk", "bucket_label": "2026-03-30"},
            )
            self.assertEqual(payload["meta"]["source_mode"], "snapshot")
            self.assertEqual(payload["meta"]["snapshot_date"], self.snapshot_date)
            self.assertEqual(len(payload["rows"]), 1)
            self.assertEqual(payload["rows"][0]["group_type"], "topic")
            self.assertEqual(payload["rows"][0]["group_key"], "climate risk")
            self.assertEqual(payload["rows"][0]["group"], "Climate Risk")
            self.assertEqual(payload["rows"][0]["bucket_label"], "2026-03-30")
            self.assertEqual(payload["rows"][0]["bucket_status"], "ok")
            self.assertEqual(payload["rows"][0]["bucket_n_articles"], 2)
        finally:
            self.snapshot_payload_path.write_text(original_payload, encoding="utf-8")
            self.client.get(f"/api/news/stats?refresh=1&snapshot_date={self.snapshot_date}")

    def test_export_snapshot_group_temporal_buckets_supports_bucket_label_filters_without_group_key(self):
        original_payload = self.snapshot_payload_path.read_text(encoding="utf-8")
        try:
            self.snapshot_payload_path.write_text(json.dumps(_sparse_bucket_temporal_payload()), encoding="utf-8")
            exported = self.client.get(
                f"/api/news/export?artifact=group_temporal_buckets&format=json&refresh=1"
                f"&bucket_label=2026-04-06&snapshot_date={self.snapshot_date}"
            )
            self.assertEqual(exported.status_code, 200)

            payload = exported.json()
            self.assertEqual(payload["artifact"], "group_temporal_buckets")
            self.assertEqual(payload["filters"], {"bucket_label": "2026-04-06"})
            self.assertEqual(payload["meta"]["source_mode"], "snapshot")
            self.assertEqual(payload["meta"]["snapshot_date"], self.snapshot_date)
            self.assertEqual(len(payload["rows"]), 6)
            self.assertEqual({row["group_type"] for row in payload["rows"]}, {"source", "topic", "tag"})
            self.assertEqual(
                {row["group_key"] for row in payload["rows"]},
                {"source a", "source b", "policy", "markets", "risk", "growth"},
            )
            self.assertTrue(all(row["bucket_label"] == "2026-04-06" for row in payload["rows"]))
            self.assertEqual(sum(1 for row in payload["rows"] if row["bucket_status"] == "sparse"), 3)
        finally:
            self.snapshot_payload_path.write_text(original_payload, encoding="utf-8")
            self.client.get(f"/api/news/stats?refresh=1&snapshot_date={self.snapshot_date}")

    def test_export_snapshot_group_temporal_buckets_csv_keeps_group_filters(self):
        original_payload = self.snapshot_payload_path.read_text(encoding="utf-8")
        try:
            self.snapshot_payload_path.write_text(json.dumps(_sparse_bucket_temporal_payload()), encoding="utf-8")
            exported = self.client.get(
                f"/api/news/export?artifact=group_temporal_buckets&format=csv&refresh=1"
                f"&group_type=tag&group_key=risk&snapshot_date={self.snapshot_date}"
            )
            self.assertEqual(exported.status_code, 200)
            self.assertIn("text/csv", exported.headers.get("content-type", ""))
            self.assertEqual(exported.headers.get("cache-control"), "no-store")
            self.assertIn(
                "group_temporal_buckets.csv",
                exported.headers.get("content-disposition", ""),
            )

            reader = csv.DictReader(io.StringIO(exported.text))
            self.assertIsNotNone(reader.fieldnames)
            self.assertIn("group_type", reader.fieldnames)
            self.assertIn("group_key", reader.fieldnames)
            self.assertIn("group_sparse_bucket_count", reader.fieldnames)
            self.assertIn("group_coverage_gap_labels", reader.fieldnames)
            self.assertIn("group_popularity_recent_share_delta", reader.fieldnames)
            self.assertIn("bucket_source_counts_json", reader.fieldnames)

            rows = list(reader)
            self.assertEqual(len(rows), 3)
            self.assertTrue(all(row["group_type"] == "tag" for row in rows))
            self.assertTrue(all(row["group_key"] == "risk" for row in rows))
            self.assertTrue(all(row["group"] == "Risk" for row in rows))

            sparse_row = next(row for row in rows if row["bucket_status"] == "sparse")
            self.assertEqual(sparse_row["bucket_start"], "2026-04-06")
            self.assertEqual(sparse_row["bucket_n_articles"], "1")
            self.assertEqual(sparse_row["group_sparse_bucket_count"], "1")
            self.assertEqual(sparse_row["group_coverage_gap_count"], "1")
            self.assertEqual(sparse_row["group_coverage_gap_labels"], "2026-04-13")
            self.assertIn('"label": "2026-04-13"', sparse_row["group_coverage_gap_ranges_json"])
            self.assertEqual(sparse_row["group_popularity_peak_bucket"], "2026-03-30")
            self.assertAlmostEqual(float(sparse_row["group_popularity_recent_share_delta"]), 1 / 6)
            self.assertIn('"Source A": 1', sparse_row["bucket_source_counts_json"])
        finally:
            self.snapshot_payload_path.write_text(original_payload, encoding="utf-8")
            self.client.get(f"/api/news/stats?refresh=1&snapshot_date={self.snapshot_date}")

    def test_export_snapshot_group_temporal_buckets_csv_keeps_source_filters(self):
        original_payload = self.snapshot_payload_path.read_text(encoding="utf-8")
        try:
            self.snapshot_payload_path.write_text(json.dumps(_sparse_bucket_temporal_payload()), encoding="utf-8")
            exported = self.client.get(
                f"/api/news/export?artifact=group_temporal_buckets&format=csv&refresh=1"
                f"&group_type=source&group_key=source-a&snapshot_date={self.snapshot_date}"
            )
            self.assertEqual(exported.status_code, 200)
            self.assertIn("text/csv", exported.headers.get("content-type", ""))
            self.assertEqual(exported.headers.get("cache-control"), "no-store")
            self.assertIn(
                "group_temporal_buckets.csv",
                exported.headers.get("content-disposition", ""),
            )

            reader = csv.DictReader(io.StringIO(exported.text))
            self.assertIsNotNone(reader.fieldnames)
            self.assertIn("group_type", reader.fieldnames)
            self.assertIn("group_key", reader.fieldnames)
            self.assertIn("group_sparse_bucket_count", reader.fieldnames)
            self.assertIn("group_coverage_gap_labels", reader.fieldnames)
            self.assertIn("group_popularity_recent_share_delta", reader.fieldnames)
            self.assertIn("bucket_source_counts_json", reader.fieldnames)

            rows = list(reader)
            self.assertEqual(len(rows), 3)
            self.assertTrue(all(row["group_type"] == "source" for row in rows))
            self.assertTrue(all(row["group_key"] == "source a" for row in rows))
            self.assertTrue(all(row["group"] == "Source A" for row in rows))

            sparse_row = next(row for row in rows if row["bucket_status"] == "sparse")
            self.assertEqual(sparse_row["bucket_start"], "2026-04-06")
            self.assertEqual(sparse_row["bucket_n_articles"], "1")
            self.assertEqual(sparse_row["group_sparse_bucket_count"], "1")
            self.assertEqual(sparse_row["group_coverage_gap_count"], "1")
            self.assertEqual(sparse_row["group_coverage_gap_labels"], "2026-04-13")
            self.assertIn('"label": "2026-04-13"', sparse_row["group_coverage_gap_ranges_json"])
            self.assertEqual(sparse_row["group_popularity_peak_bucket"], "2026-03-30")
            self.assertAlmostEqual(float(sparse_row["group_popularity_recent_share_delta"]), 1 / 6)
            self.assertIn('"Source A": 1', sparse_row["bucket_source_counts_json"])
        finally:
            self.snapshot_payload_path.write_text(original_payload, encoding="utf-8")
            self.client.get(f"/api/news/stats?refresh=1&snapshot_date={self.snapshot_date}")

    def test_export_snapshot_group_temporal_buckets_csv_normalizes_source_group_key_variants(self):
        original_payload = self.snapshot_payload_path.read_text(encoding="utf-8")
        try:
            self.snapshot_payload_path.write_text(json.dumps(_sparse_bucket_temporal_payload()), encoding="utf-8")
            exported = self.client.get(
                f"/api/news/export?artifact=group_temporal_buckets&format=csv&refresh=1"
                f"&group_type=source&group_key=Source_A&snapshot_date={self.snapshot_date}"
            )
            self.assertEqual(exported.status_code, 200)
            self.assertIn("text/csv", exported.headers.get("content-type", ""))
            self.assertEqual(exported.headers.get("cache-control"), "no-store")
            self.assertIn(
                "group_temporal_buckets.csv",
                exported.headers.get("content-disposition", ""),
            )

            reader = csv.DictReader(io.StringIO(exported.text))
            self.assertIsNotNone(reader.fieldnames)
            self.assertIn("group_type", reader.fieldnames)
            self.assertIn("group_key", reader.fieldnames)
            self.assertIn("group_sparse_bucket_count", reader.fieldnames)
            self.assertIn("group_coverage_gap_labels", reader.fieldnames)
            self.assertIn("group_popularity_recent_share_delta", reader.fieldnames)
            self.assertIn("bucket_source_counts_json", reader.fieldnames)

            rows = list(reader)
            self.assertEqual(len(rows), 3)
            self.assertTrue(all(row["group_type"] == "source" for row in rows))
            self.assertTrue(all(row["group_key"] == "source a" for row in rows))
            self.assertTrue(all(row["group"] == "Source A" for row in rows))

            sparse_row = next(row for row in rows if row["bucket_status"] == "sparse")
            self.assertEqual(sparse_row["bucket_start"], "2026-04-06")
            self.assertEqual(sparse_row["bucket_n_articles"], "1")
            self.assertEqual(sparse_row["group_sparse_bucket_count"], "1")
            self.assertEqual(sparse_row["group_coverage_gap_count"], "1")
            self.assertEqual(sparse_row["group_coverage_gap_labels"], "2026-04-13")
            self.assertIn('"label": "2026-04-13"', sparse_row["group_coverage_gap_ranges_json"])
            self.assertEqual(sparse_row["group_popularity_peak_bucket"], "2026-03-30")
            self.assertAlmostEqual(float(sparse_row["group_popularity_recent_share_delta"]), 1 / 6)
            self.assertIn('"Source A": 1', sparse_row["bucket_source_counts_json"])
        finally:
            self.snapshot_payload_path.write_text(original_payload, encoding="utf-8")
            self.client.get(f"/api/news/stats?refresh=1&snapshot_date={self.snapshot_date}")

    def test_export_snapshot_group_temporal_buckets_csv_keeps_topic_filters(self):
        original_payload = self.snapshot_payload_path.read_text(encoding="utf-8")
        try:
            self.snapshot_payload_path.write_text(json.dumps(_sparse_bucket_temporal_payload()), encoding="utf-8")
            exported = self.client.get(
                f"/api/news/export?artifact=group_temporal_buckets&format=csv&refresh=1"
                f"&group_type=topic&group_key=policy&snapshot_date={self.snapshot_date}"
            )
            self.assertEqual(exported.status_code, 200)
            self.assertIn("text/csv", exported.headers.get("content-type", ""))
            self.assertEqual(exported.headers.get("cache-control"), "no-store")
            self.assertIn(
                "group_temporal_buckets.csv",
                exported.headers.get("content-disposition", ""),
            )

            reader = csv.DictReader(io.StringIO(exported.text))
            self.assertIsNotNone(reader.fieldnames)
            self.assertIn("group_type", reader.fieldnames)
            self.assertIn("group_key", reader.fieldnames)
            self.assertIn("group_sparse_bucket_count", reader.fieldnames)
            self.assertIn("group_coverage_gap_labels", reader.fieldnames)
            self.assertIn("group_popularity_recent_share_delta", reader.fieldnames)
            self.assertIn("bucket_source_counts_json", reader.fieldnames)

            rows = list(reader)
            self.assertEqual(len(rows), 3)
            self.assertTrue(all(row["group_type"] == "topic" for row in rows))
            self.assertTrue(all(row["group_key"] == "policy" for row in rows))
            self.assertTrue(all(row["group"] == "Policy" for row in rows))

            sparse_row = next(row for row in rows if row["bucket_status"] == "sparse")
            self.assertEqual(sparse_row["bucket_start"], "2026-04-06")
            self.assertEqual(sparse_row["bucket_n_articles"], "1")
            self.assertEqual(sparse_row["group_sparse_bucket_count"], "1")
            self.assertEqual(sparse_row["group_coverage_gap_count"], "1")
            self.assertEqual(sparse_row["group_coverage_gap_labels"], "2026-04-13")
            self.assertIn('"label": "2026-04-13"', sparse_row["group_coverage_gap_ranges_json"])
            self.assertEqual(sparse_row["group_popularity_peak_bucket"], "2026-03-30")
            self.assertAlmostEqual(float(sparse_row["group_popularity_recent_share_delta"]), 1 / 6)
            self.assertIn('"Source A": 1', sparse_row["bucket_source_counts_json"])
        finally:
            self.snapshot_payload_path.write_text(original_payload, encoding="utf-8")
            self.client.get(f"/api/news/stats?refresh=1&snapshot_date={self.snapshot_date}")

    def test_export_snapshot_group_temporal_buckets_csv_supports_bucket_label_filters_for_multi_word_topic_keys(self):
        original_payload = self.snapshot_payload_path.read_text(encoding="utf-8")
        try:
            self.snapshot_payload_path.write_text(
                json.dumps(_sparse_bucket_temporal_payload_with_multi_word_topic()),
                encoding="utf-8",
            )
            exported = self.client.get(
                f"/api/news/export?artifact=group_temporal_buckets&format=csv&refresh=1"
                f"&group_type=topic&group_key=Climate_Risk&bucket_label=2026-03-30&snapshot_date={self.snapshot_date}"
            )
            self.assertEqual(exported.status_code, 200)
            self.assertIn("text/csv", exported.headers.get("content-type", ""))
            self.assertEqual(exported.headers.get("cache-control"), "no-store")

            rows = list(csv.DictReader(io.StringIO(exported.text)))
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]["group_type"], "topic")
            self.assertEqual(rows[0]["group_key"], "climate risk")
            self.assertEqual(rows[0]["group"], "Climate Risk")
            self.assertEqual(rows[0]["bucket_label"], "2026-03-30")
            self.assertEqual(rows[0]["bucket_status"], "ok")
            self.assertEqual(rows[0]["bucket_n_articles"], "2")
        finally:
            self.snapshot_payload_path.write_text(original_payload, encoding="utf-8")
            self.client.get(f"/api/news/stats?refresh=1&snapshot_date={self.snapshot_date}")

    def test_export_snapshot_group_temporal_buckets_csv_supports_bucket_label_filters_without_group_key(self):
        original_payload = self.snapshot_payload_path.read_text(encoding="utf-8")
        try:
            self.snapshot_payload_path.write_text(json.dumps(_sparse_bucket_temporal_payload()), encoding="utf-8")
            exported = self.client.get(
                f"/api/news/export?artifact=group_temporal_buckets&format=csv&refresh=1"
                f"&bucket_label=2026-04-06&snapshot_date={self.snapshot_date}"
            )
            self.assertEqual(exported.status_code, 200)
            self.assertIn("text/csv", exported.headers.get("content-type", ""))
            self.assertEqual(exported.headers.get("cache-control"), "no-store")

            rows = list(csv.DictReader(io.StringIO(exported.text)))
            self.assertEqual(len(rows), 6)
            self.assertEqual({row["group_type"] for row in rows}, {"source", "topic", "tag"})
            self.assertEqual({row["group_key"] for row in rows}, {"source a", "source b", "policy", "markets", "risk", "growth"})
            self.assertTrue(all(row["bucket_label"] == "2026-04-06" for row in rows))
            self.assertEqual(sum(1 for row in rows if row["bucket_status"] == "sparse"), 3)
        finally:
            self.snapshot_payload_path.write_text(original_payload, encoding="utf-8")
            self.client.get(f"/api/news/stats?refresh=1&snapshot_date={self.snapshot_date}")

    def test_export_snapshot_group_temporal_path_summary_csv_keeps_group_filters(self):
        original_payload = self.snapshot_payload_path.read_text(encoding="utf-8")
        try:
            self.snapshot_payload_path.write_text(json.dumps(_sparse_bucket_temporal_payload()), encoding="utf-8")
            exported = self.client.get(
                f"/api/news/export?artifact=group_temporal_path_summary&format=csv&refresh=1"
                f"&group_type=tag&group_key=risk&snapshot_date={self.snapshot_date}"
            )
            self.assertEqual(exported.status_code, 200)
            self.assertIn("text/csv", exported.headers.get("content-type", ""))
            self.assertEqual(exported.headers.get("cache-control"), "no-store")
            self.assertIn(
                "group_temporal_path_summary.csv",
                exported.headers.get("content-disposition", ""),
            )

            reader = csv.DictReader(io.StringIO(exported.text))
            self.assertIsNotNone(reader.fieldnames)
            self.assertIn("group_type", reader.fieldnames)
            self.assertIn("group_key", reader.fieldnames)
            self.assertIn("coverage_gap_labels", reader.fieldnames)
            self.assertIn("coverage_gap_ranges_json", reader.fieldnames)
            self.assertIn("popularity_recent_share_delta", reader.fieldnames)

            rows = list(reader)
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]["group_type"], "tag")
            self.assertEqual(rows[0]["group_key"], "risk")
            self.assertEqual(rows[0]["group"], "Risk")
            self.assertEqual(rows[0]["coverage_gap_count"], "1")
            self.assertEqual(rows[0]["coverage_gap_labels"], "2026-04-13")
            self.assertIn('"label": "2026-04-13"', rows[0]["coverage_gap_ranges_json"])
            self.assertEqual(rows[0]["popularity_peak_bucket"], "2026-03-30")
            self.assertAlmostEqual(float(rows[0]["popularity_recent_share_delta"]), 1 / 6)
        finally:
            self.snapshot_payload_path.write_text(original_payload, encoding="utf-8")
            self.client.get(f"/api/news/stats?refresh=1&snapshot_date={self.snapshot_date}")

    def test_export_snapshot_group_temporal_path_summary_csv_keeps_source_filters(self):
        original_payload = self.snapshot_payload_path.read_text(encoding="utf-8")
        try:
            self.snapshot_payload_path.write_text(json.dumps(_sparse_bucket_temporal_payload()), encoding="utf-8")
            exported = self.client.get(
                f"/api/news/export?artifact=group_temporal_path_summary&format=csv&refresh=1"
                f"&group_type=source&group_key=source-a&snapshot_date={self.snapshot_date}"
            )
            self.assertEqual(exported.status_code, 200)
            self.assertIn("text/csv", exported.headers.get("content-type", ""))
            self.assertEqual(exported.headers.get("cache-control"), "no-store")
            self.assertIn(
                "group_temporal_path_summary.csv",
                exported.headers.get("content-disposition", ""),
            )

            reader = csv.DictReader(io.StringIO(exported.text))
            self.assertIsNotNone(reader.fieldnames)
            self.assertIn("group_type", reader.fieldnames)
            self.assertIn("group_key", reader.fieldnames)
            self.assertIn("coverage_gap_labels", reader.fieldnames)
            self.assertIn("coverage_gap_ranges_json", reader.fieldnames)
            self.assertIn("popularity_recent_share_delta", reader.fieldnames)

            rows = list(reader)
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]["group_type"], "source")
            self.assertEqual(rows[0]["group_key"], "source a")
            self.assertEqual(rows[0]["group"], "Source A")
            self.assertEqual(rows[0]["coverage_gap_count"], "1")
            self.assertEqual(rows[0]["coverage_gap_labels"], "2026-04-13")
            self.assertIn('"label": "2026-04-13"', rows[0]["coverage_gap_ranges_json"])
            self.assertEqual(rows[0]["popularity_peak_bucket"], "2026-03-30")
            self.assertEqual(rows[0]["popularity_peak_articles"], "2")
            self.assertEqual(rows[0]["popularity_first_share"], "0.5")
            self.assertEqual(rows[0]["popularity_latest_share"], "0.5")
            self.assertAlmostEqual(float(rows[0]["popularity_recent_share_delta"]), 1 / 6)
        finally:
            self.snapshot_payload_path.write_text(original_payload, encoding="utf-8")
            self.client.get(f"/api/news/stats?refresh=1&snapshot_date={self.snapshot_date}")

    def test_export_snapshot_group_temporal_path_summary_csv_normalizes_source_group_key_variants(self):
        original_payload = self.snapshot_payload_path.read_text(encoding="utf-8")
        try:
            self.snapshot_payload_path.write_text(json.dumps(_sparse_bucket_temporal_payload()), encoding="utf-8")
            exported = self.client.get(
                f"/api/news/export?artifact=group_temporal_path_summary&format=csv&refresh=1"
                f"&group_type=source&group_key=Source_A&snapshot_date={self.snapshot_date}"
            )
            self.assertEqual(exported.status_code, 200)
            self.assertIn("text/csv", exported.headers.get("content-type", ""))
            self.assertEqual(exported.headers.get("cache-control"), "no-store")
            self.assertIn(
                "group_temporal_path_summary.csv",
                exported.headers.get("content-disposition", ""),
            )

            reader = csv.DictReader(io.StringIO(exported.text))
            self.assertIsNotNone(reader.fieldnames)
            self.assertIn("group_type", reader.fieldnames)
            self.assertIn("group_key", reader.fieldnames)
            self.assertIn("coverage_gap_labels", reader.fieldnames)
            self.assertIn("coverage_gap_ranges_json", reader.fieldnames)
            self.assertIn("popularity_recent_share_delta", reader.fieldnames)

            rows = list(reader)
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]["group_type"], "source")
            self.assertEqual(rows[0]["group_key"], "source a")
            self.assertEqual(rows[0]["group"], "Source A")
            self.assertEqual(rows[0]["coverage_gap_count"], "1")
            self.assertEqual(rows[0]["coverage_gap_labels"], "2026-04-13")
            self.assertIn('"label": "2026-04-13"', rows[0]["coverage_gap_ranges_json"])
            self.assertEqual(rows[0]["popularity_peak_bucket"], "2026-03-30")
            self.assertEqual(rows[0]["popularity_peak_articles"], "2")
            self.assertEqual(rows[0]["popularity_first_share"], "0.5")
            self.assertEqual(rows[0]["popularity_latest_share"], "0.5")
            self.assertAlmostEqual(float(rows[0]["popularity_recent_share_delta"]), 1 / 6)
        finally:
            self.snapshot_payload_path.write_text(original_payload, encoding="utf-8")
            self.client.get(f"/api/news/stats?refresh=1&snapshot_date={self.snapshot_date}")

    def test_export_snapshot_group_temporal_path_summary_csv_keeps_topic_filters(self):
        original_payload = self.snapshot_payload_path.read_text(encoding="utf-8")
        try:
            self.snapshot_payload_path.write_text(json.dumps(_sparse_bucket_temporal_payload()), encoding="utf-8")
            exported = self.client.get(
                f"/api/news/export?artifact=group_temporal_path_summary&format=csv&refresh=1"
                f"&group_type=topic&group_key=policy&snapshot_date={self.snapshot_date}"
            )
            self.assertEqual(exported.status_code, 200)
            self.assertIn("text/csv", exported.headers.get("content-type", ""))
            self.assertEqual(exported.headers.get("cache-control"), "no-store")
            self.assertIn(
                "group_temporal_path_summary.csv",
                exported.headers.get("content-disposition", ""),
            )

            reader = csv.DictReader(io.StringIO(exported.text))
            self.assertIsNotNone(reader.fieldnames)
            self.assertIn("group_type", reader.fieldnames)
            self.assertIn("group_key", reader.fieldnames)
            self.assertIn("coverage_gap_labels", reader.fieldnames)
            self.assertIn("coverage_gap_ranges_json", reader.fieldnames)
            self.assertIn("popularity_recent_share_delta", reader.fieldnames)

            rows = list(reader)
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]["group_type"], "topic")
            self.assertEqual(rows[0]["group_key"], "policy")
            self.assertEqual(rows[0]["group"], "Policy")
            self.assertEqual(rows[0]["coverage_gap_count"], "1")
            self.assertEqual(rows[0]["coverage_gap_labels"], "2026-04-13")
            self.assertIn('"label": "2026-04-13"', rows[0]["coverage_gap_ranges_json"])
            self.assertEqual(rows[0]["popularity_peak_bucket"], "2026-03-30")
            self.assertEqual(rows[0]["popularity_peak_articles"], "2")
            self.assertEqual(rows[0]["popularity_first_share"], "0.5")
            self.assertEqual(rows[0]["popularity_latest_share"], "0.5")
            self.assertAlmostEqual(float(rows[0]["popularity_recent_share_delta"]), 1 / 6)
        finally:
            self.snapshot_payload_path.write_text(original_payload, encoding="utf-8")
            self.client.get(f"/api/news/stats?refresh=1&snapshot_date={self.snapshot_date}")

    def test_export_rejects_group_key_without_group_type(self):
        response = self.client.get(
            "/api/news/export?artifact=group_temporal_popularity_momentum&format=json&group_key=risk"
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["status"], "bad_request")
        self.assertIn("group_key requires group_type", response.json()["error"])

    def test_stats_precomputed_mode_serves_snapshot_and_missing_falls_back(self):
        snapshot_payload = {
            "status": "ok",
            "meta": {"source_url": "file://precomputed.json", "source_mode": "current", "generated_at": NOW_UTC_ISO},
            "data": {
                "derived": {
                    "total_articles": 1,
                    "tag_sliced_analysis": {"summary": {"tag_count": 0}},
                    "event_control": {
                        "status": "ok",
                        "reason": "",
                        "summary": {
                            "total_articles_considered": 3,
                            "embedded_count": 3,
                            "event_count": 1,
                            "multi_source_event_count": 1,
                            "singleton_count": 1,
                        },
                        "cache": {"enabled": True, "hits": 3, "misses": 0, "stored": 0},
                        "config": {
                            "embedding_model": "test-model",
                            "embedding_dimensions": 3,
                            "similarity_threshold": 0.86,
                            "date_window_days": 3,
                        },
                    },
                },
                "summary": {},
                "analysis": {},
            },
        }
        precomputed_path = self.temp_dir / "precomputed_stats.json"
        precomputed_path.write_text(json.dumps(snapshot_payload), encoding="utf-8")

        previous_backend = os.environ.get("NEWS_STATS_BACKEND")
        previous_path = os.environ.get("NEWS_STATS_SNAPSHOT_PATH")
        try:
            os.environ["NEWS_STATS_BACKEND"] = "precomputed"
            os.environ["NEWS_STATS_SNAPSHOT_PATH"] = str(precomputed_path)
            response = self.client.get("/api/news/stats")
            self.assertEqual(response.status_code, 200)
            self.assertIn("public, max-age=", response.headers.get("cache-control", ""))
            payload = response.json()
            self.assertEqual(payload["status"], "ok")
            self.assertEqual(payload["data"]["derived"]["total_articles"], 1)
            self.assertEqual(payload["meta"]["stats_backend"], "precomputed")

            refreshed = self.client.get("/api/news/stats?refresh=1")
            self.assertEqual(refreshed.status_code, 200)
            self.assertEqual(refreshed.headers.get("cache-control"), "no-store")
            refreshed_payload = refreshed.json()
            self.assertEqual(refreshed_payload["status"], "ok")
            self.assertNotEqual(refreshed_payload["meta"].get("stats_backend"), "precomputed")
            self.assertIsInstance(refreshed_payload["data"]["derived"], dict)

            exported = self.client.get("/api/news/export?artifact=event_control_summary&format=json")
            self.assertEqual(exported.status_code, 200)
            export_payload = exported.json()
            self.assertEqual(export_payload["meta"]["stats_backend"], "precomputed")
            self.assertEqual(export_payload["rows"][0]["event_count"], 1)
            self.assertEqual(export_payload["rows"][0]["cache_hits"], 3)

            stale_payload = dict(snapshot_payload)
            stale_payload["meta"] = dict(snapshot_payload["meta"])
            stale_payload["meta"]["generated_at"] = "2026-01-01T00:00:00Z"
            precomputed_path.write_text(json.dumps(stale_payload), encoding="utf-8")
            stale = self.client.get("/api/news/stats")
            self.assertEqual(stale.status_code, 200)
            self.assertEqual(stale.headers.get("cache-control"), "no-store")
            stale_payload_response = stale.json()
            self.assertEqual(stale_payload_response["status"], "ok")
            self.assertEqual(stale_payload_response["meta"]["stats_backend"], "dynamic")
            self.assertEqual(stale_payload_response["meta"]["stats_backend_fallback"], "precomputed_unavailable")
            self.assertIn("snapshot is stale", stale_payload_response["meta"]["precomputed_stats_error"])

            os.environ["NEWS_STATS_SNAPSHOT_PATH"] = str(self.temp_dir / "missing_precomputed_stats.json")
            missing = self.client.get("/api/news/stats")
            self.assertEqual(missing.status_code, 200)
            self.assertEqual(missing.headers.get("cache-control"), "no-store")
            missing_payload = missing.json()
            self.assertEqual(missing_payload["status"], "ok")
            self.assertEqual(missing_payload["meta"]["stats_backend"], "dynamic")
            self.assertEqual(missing_payload["meta"]["stats_backend_fallback"], "precomputed_unavailable")
            self.assertIn("missing_precomputed_stats.json", missing_payload["meta"]["precomputed_stats_error"])
            self.assertIsInstance(missing_payload["data"]["derived"], dict)

            missing_export = self.client.get("/api/news/export?artifact=event_control_summary&format=json")
            self.assertEqual(missing_export.status_code, 200)
            self.assertEqual(missing_export.headers.get("cache-control"), "no-store")
            missing_export_payload = missing_export.json()
            self.assertEqual(missing_export_payload["status"], "ok")
            self.assertEqual(missing_export_payload["meta"]["stats_backend"], "dynamic")
            self.assertEqual(missing_export_payload["meta"]["stats_backend_fallback"], "precomputed_unavailable")
            self.assertIn("missing_precomputed_stats.json", missing_export_payload["meta"]["precomputed_stats_error"])
            self.assertIsInstance(missing_export_payload["rows"], list)
        finally:
            if previous_backend is None:
                os.environ.pop("NEWS_STATS_BACKEND", None)
            else:
                os.environ["NEWS_STATS_BACKEND"] = previous_backend
            if previous_path is None:
                os.environ.pop("NEWS_STATS_SNAPSHOT_PATH", None)
            else:
                os.environ["NEWS_STATS_SNAPSHOT_PATH"] = previous_path

    def test_export_csv_and_freshness(self):
        exported = self.client.get("/api/news/export?artifact=source_differentiation_summary&format=csv")
        self.assertEqual(exported.status_code, 200)
        self.assertTrue(exported.headers.get("content-type", "").startswith("text/csv"))
        self.assertIn("attachment; filename=\"source_differentiation_summary.csv\"", exported.headers.get("content-disposition", ""))

        freshness = self.client.get("/health/news-freshness")
        self.assertIn(freshness.status_code, {200, 503})
        freshness_payload = freshness.json()
        self.assertIn("status", freshness_payload)
        self.assertIn("is_fresh", freshness_payload)


if __name__ == "__main__":
    unittest.main()
