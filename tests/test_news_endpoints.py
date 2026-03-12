import json
import os
import shutil
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from flask import Flask

from src.api.news_endpoints import register_news_endpoints


NOW_UTC = datetime.now(timezone.utc)
NOW_UTC_ISO = NOW_UTC.isoformat().replace("+00:00", "Z")
DIGEST_UTC_ISO = (NOW_UTC - timedelta(minutes=3)).isoformat().replace("+00:00", "Z")


SAMPLE_PAYLOAD = {
    "schema_version": "1.0",
    "generated_at": NOW_UTC_ISO,
    "contract": "rss_pipeline_precomputed",
    "digest": {
        "generated_at": DIGEST_UTC_ISO,
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
        cls.temp_dir = Path(tempfile.mkdtemp(prefix="rss-news-endpoints-"))
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

        app = Flask(__name__)
        register_news_endpoints(app)
        cls.client = app.test_client()

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.temp_dir, ignore_errors=True)

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

    def test_snapshot_date_routing_and_meta(self):
        response = self.client.get(f"/api/news/digest?snapshot_date={self.snapshot_date}")
        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertEqual(payload["status"], "ok")
        self.assertEqual(payload["filters"]["snapshot_date"], self.snapshot_date)
        self.assertEqual(payload["meta"]["source_mode"], "snapshot")
        self.assertEqual(payload["meta"]["snapshot_date"], self.snapshot_date)
        self.assertIn(f"rss_openai_daily_{self.snapshot_date}.json", payload["meta"]["source_url"])

        latest = self.client.get(f"/api/news/digest/latest?snapshot_date={self.snapshot_date}")
        self.assertEqual(latest.status_code, 200)
        self.assertEqual(latest.get_json()["meta"]["source_mode"], "snapshot")

        stats = self.client.get(f"/api/news/stats?snapshot_date={self.snapshot_date}")
        self.assertEqual(stats.status_code, 200)
        self.assertEqual(stats.get_json()["meta"]["source_mode"], "snapshot")

    def test_snapshot_date_validation_and_missing_file(self):
        bad_date = self.client.get("/api/news/digest?snapshot_date=2026/03/10")
        self.assertEqual(bad_date.status_code, 400)
        self.assertEqual(bad_date.get_json()["status"], "bad_request")

        missing_snapshot = self.client.get("/api/news/digest?snapshot_date=2026-03-09")
        self.assertEqual(missing_snapshot.status_code, 404)
        self.assertEqual(missing_snapshot.get_json()["status"], "not_found")

        missing_stats = self.client.get("/api/news/stats?snapshot_date=2026-03-09")
        self.assertEqual(missing_stats.status_code, 404)
        self.assertEqual(missing_stats.get_json()["status"], "not_found")

    def test_stats_and_freshness(self):
        stats = self.client.get("/api/news/stats")
        self.assertEqual(stats.status_code, 200)
        stats_payload = stats.get_json()
        self.assertEqual(stats_payload["status"], "ok")
        self.assertIn("derived", stats_payload["data"])
        chart_aggregates = stats_payload["data"]["derived"]["chart_aggregates"]
        self.assertEqual(len(chart_aggregates["score_histogram_bins"]), 10)
        self.assertEqual(len(chart_aggregates["tag_count_distribution"]), 6)
        self.assertEqual(len(chart_aggregates["publish_hour_counts_utc"]), 24)
        self.assertEqual(len(chart_aggregates["score_tag_count_heatmap"]), 25)

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
