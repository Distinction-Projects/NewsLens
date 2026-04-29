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

        snapshot = self.client.get(f"/api/news/stats?snapshot_date={self.snapshot_date}")
        self.assertEqual(snapshot.status_code, 200)
        snapshot_payload = snapshot.json()
        self.assertEqual(snapshot_payload["meta"]["source_mode"], "snapshot")
        self.assertEqual(snapshot_payload["meta"]["snapshot_date"], self.snapshot_date)

        missing_snapshot = self.client.get("/api/news/stats?snapshot_date=2026-03-09")
        self.assertEqual(missing_snapshot.status_code, 404)
        self.assertEqual(missing_snapshot.json()["status"], "not_found")

    def test_stats_precomputed_mode_serves_snapshot_and_missing_returns_503(self):
        snapshot_payload = {
            "status": "ok",
            "meta": {"source_url": "file://precomputed.json", "source_mode": "current"},
            "data": {
                "derived": {"total_articles": 1, "tag_sliced_analysis": {"summary": {"tag_count": 0}}},
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

            os.environ["NEWS_STATS_SNAPSHOT_PATH"] = str(self.temp_dir / "missing_precomputed_stats.json")
            missing = self.client.get("/api/news/stats")
            self.assertEqual(missing.status_code, 503)
            self.assertEqual(missing.headers.get("cache-control"), "no-store")
            self.assertEqual(missing.json()["status"], "precomputed_stats_unavailable")
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
