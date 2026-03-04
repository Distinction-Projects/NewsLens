import json
import tempfile
import unittest
from pathlib import Path

from src.services.rss_digest import (
    RssDigestClient,
    derive_stats,
    filter_records,
    normalize_articles,
    parse_datetime,
    sort_records_desc,
)


SAMPLE_PAYLOAD = {
    "schema_version": "1.0",
    "generated_at": "2026-03-02T20:54:00Z",
    "contract": "rss_pipeline_precomputed",
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


class RssDigestServiceTests(unittest.TestCase):
    def test_parse_datetime_supports_rfc2822(self):
        parsed = parse_datetime("Mon, 02 Mar 2026 15:25:29 -0500")
        self.assertIsNotNone(parsed)
        self.assertEqual(parsed.isoformat().replace("+00:00", "Z"), "2026-03-02T20:25:29Z")

    def test_normalize_and_filter_semantics(self):
        records = normalize_articles(SAMPLE_PAYLOAD)
        self.assertEqual(len(records), 2)
        self.assertEqual(records[0]["source"]["name"], "PBS NewsHour")
        self.assertIn("OpenAI", records[0]["tags"])

        by_date = filter_records(records, date_filter="2026-03-02")
        self.assertEqual(len(by_date), 1)
        self.assertEqual(by_date[0]["id"], "a-1")

        by_tag = filter_records(records, tag_filter="openai")
        self.assertEqual(len(by_tag), 2)

        by_source = filter_records(records, source_filter="pbs")
        self.assertEqual(len(by_source), 1)
        self.assertEqual(by_source[0]["id"], "a-1")

    def test_date_filter_uses_utc(self):
        payload = {
            "articles": [
                {
                    "id": "tz-1",
                    "title": "TZ case",
                    "published": "Sun, 01 Mar 2026 23:30:00 -0500",
                    "ai_tags": ["OpenAI"],
                    "topic_tags": [],
                    "source": {"id": "tz-source", "name": "TZ Source"},
                    "feed": {"name": "TZ Feed", "url": "https://example.com/tz"},
                    "score": {"value": 1, "max_value": 1, "percent": 100, "rubric_count": 1},
                }
            ]
        }
        records = normalize_articles(payload)
        matched = filter_records(records, date_filter="2026-03-02")
        self.assertEqual(len(matched), 1)

    def test_sort_and_stats(self):
        records = normalize_articles(SAMPLE_PAYLOAD)
        ordered = sort_records_desc(records)
        self.assertEqual(ordered[0]["id"], "a-1")

        stats = derive_stats(ordered, SAMPLE_PAYLOAD)
        self.assertEqual(stats["total_articles"], 2)
        self.assertEqual(stats["scored_articles"], 2)
        self.assertEqual(stats["high_scoring_articles"], 1)
        self.assertTrue(stats["source_counts"])
        self.assertTrue(stats["tag_counts"])
        self.assertEqual(stats["score_distribution"]["count"], 2)

    def test_last_good_fallback(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as temp:
            json.dump(SAMPLE_PAYLOAD, temp)
            temp_path = Path(temp.name)

        client = RssDigestClient(source_url=f"file://{temp_path}", ttl_seconds=1, timeout_seconds=2)
        first = client.get_payload(force_refresh=True)
        self.assertFalse(first["using_last_good"])
        self.assertEqual(len(first["articles_normalized"]), 2)

        client.source_url = "https://127.0.0.1:1/not-available.json"
        second = client.get_payload(force_refresh=True)
        self.assertTrue(second["using_last_good"])
        self.assertTrue(second["error"])

        temp_path.unlink(missing_ok=True)


if __name__ == "__main__":
    unittest.main()
