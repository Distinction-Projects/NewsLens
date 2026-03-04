import json
import os
import tempfile
import unittest
from pathlib import Path

from flask import Flask

from src.api.news_endpoints import register_news_endpoints


SAMPLE_PAYLOAD = {
    "schema_version": "1.0",
    "generated_at": "2026-03-02T20:54:00Z",
    "contract": "rss_pipeline_precomputed",
    "digest": {
        "generated_at": "2026-03-02T20:51:24Z",
        "run_id": "digest-abc123",
    },
    "summary": {"articles": 2, "scored_articles": 2, "high_scoring_articles": 1},
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
            "score": {"value": 14.0, "max_value": 20.0, "percent": 70.0, "rubric_count": 3},
            "high_score": {"overall_score": 14.0, "overall_percent": 70.0, "lens_scores": {"L1": 7.0}},
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
            "score": {"value": 8.0, "max_value": 20.0, "percent": 40.0, "rubric_count": 3},
            "high_score": None,
        },
    ],
}


class NewsEndpointTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp_file = tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False)
        json.dump(SAMPLE_PAYLOAD, cls.temp_file)
        cls.temp_file.flush()
        cls.temp_path = Path(cls.temp_file.name)
        cls.temp_file.close()

        os.environ["RSS_DAILY_JSON_URL"] = f"file://{cls.temp_path}"
        os.environ["RSS_CACHE_TTL_SECONDS"] = "60"
        os.environ["RSS_HTTP_TIMEOUT_SECONDS"] = "5"
        os.environ["RSS_MAX_AGE_SECONDS"] = "172800"

        app = Flask(__name__)
        register_news_endpoints(app)
        cls.client = app.test_client()

    @classmethod
    def tearDownClass(cls):
        cls.temp_path.unlink(missing_ok=True)

    def test_digest_and_filters(self):
        response = self.client.get("/api/news/digest")
        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertEqual(payload["status"], "ok")
        self.assertEqual(len(payload["data"]), 2)

        response = self.client.get("/api/news/digest?tag=openai")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.get_json()["data"]), 2)

        response = self.client.get("/api/news/digest?source=pbs")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.get_json()["data"]), 1)

    def test_latest_and_bad_limit(self):
        latest = self.client.get("/api/news/digest/latest")
        self.assertEqual(latest.status_code, 200)
        self.assertEqual(latest.get_json()["data"]["id"], "a-1")

        bad_limit = self.client.get("/api/news/digest?limit=0")
        self.assertEqual(bad_limit.status_code, 400)

    def test_stats_and_freshness(self):
        stats = self.client.get("/api/news/stats")
        self.assertEqual(stats.status_code, 200)
        stats_payload = stats.get_json()
        self.assertEqual(stats_payload["status"], "ok")
        self.assertIn("derived", stats_payload["data"])

        health = self.client.get("/health/news-freshness")
        self.assertEqual(health.status_code, 200)
        health_payload = health.get_json()
        self.assertTrue(health_payload["is_fresh"])

    def test_freshness_is_stale_when_generated_at_missing(self):
        payload = dict(SAMPLE_PAYLOAD)
        payload.pop("generated_at", None)

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as temp:
            json.dump(payload, temp)
            temp.flush()
            temp_path = Path(temp.name)

        previous_url = os.environ.get("RSS_DAILY_JSON_URL")
        try:
            os.environ["RSS_DAILY_JSON_URL"] = f"file://{temp_path}"
            app = Flask(__name__)
            register_news_endpoints(app)
            client = app.test_client()

            response = client.get("/health/news-freshness?refresh=true")
            self.assertEqual(response.status_code, 503)
            body = response.get_json()
            self.assertEqual(body["status"], "stale")
            self.assertFalse(body["is_fresh"])
            self.assertEqual(body["reason"], "generated_at is missing from payload")
        finally:
            if previous_url is None:
                os.environ.pop("RSS_DAILY_JSON_URL", None)
            else:
                os.environ["RSS_DAILY_JSON_URL"] = previous_url
            temp_path.unlink(missing_ok=True)


if __name__ == "__main__":
    unittest.main()
