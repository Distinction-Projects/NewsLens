import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

from src.api.fastapi_news import _news_client_from_env
from src.api.news_controller import NewsController
from src.ingest.rss_to_postgres import import_current
from src.services.news_postgres import PostgresNewsClient
from src.services.rss_digest import RssDigestClient


class _FakeCursor:
    def __init__(self):
        self.execute_count = 0

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def execute(self, *_args, **_kwargs):
        self.execute_count += 1

    def fetchone(self):
        if self.execute_count == 1:
            return (
                "run-1",
                "current",
                None,
                "postgres://import",
                "1.0",
                "rss_pipeline_precomputed",
                datetime(2026, 4, 27, 16, 0, tzinfo=timezone.utc),
                datetime(2026, 4, 27, 15, 59, tzinfo=timezone.utc),
                "digest-1",
                datetime(2026, 4, 27, 16, 1, tzinfo=timezone.utc),
                2,
                1,
            )
        if self.execute_count == 3:
            return ({"total_articles": 2, "source_counts": []},)
        return None

    def fetchall(self):
        return [
            (
                {
                    "id": "a-older",
                    "title": "Older",
                    "published": "2026-04-26T10:00:00Z",
                    "scraped": {"body_text": "Older body"},
                    "source": {"name": "Source B"},
                },
            ),
            (
                {
                    "id": "a-newer",
                    "title": "Newer",
                    "published": "2026-04-27T10:00:00Z",
                    "scraped": {"body_text": "Newer body"},
                    "source": {"name": "Source A"},
                },
            ),
        ]


class _FakeConnection:
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def cursor(self):
        return _FakeCursor()


class _FakeJsonClient:
    def __init__(self, bundle):
        self.bundle = bundle
        self.max_age_seconds = 36 * 3600

    def get_payload(self, *, force_refresh=False, snapshot_date=None):
        return self.bundle


class DatabaseFoundationTests(unittest.TestCase):
    def test_initial_migration_defines_expected_tables(self):
        migration = Path("supabase/migrations/20260428000000_initial_newslens_schema.sql")
        self.assertTrue(migration.exists())
        sql = migration.read_text(encoding="utf-8")
        for table_name in [
            "import_runs",
            "sources",
            "feeds",
            "articles",
            "article_tags",
            "lenses",
            "rubrics",
            "article_scores",
            "snapshots",
            "derived_metrics",
            "analysis_runs",
        ]:
            self.assertIn(f"public.{table_name}", sql)

    @patch("src.ingest.rss_to_postgres.RssDigestClient")
    def test_import_current_dry_run_summarizes_without_database(self, mock_client_cls):
        mock_client = mock_client_cls.return_value
        mock_client.get_payload.return_value = {
            "source_mode": "current",
            "articles_normalized": [{"id": "a-1"}, {"id": "a-2"}],
            "stats": {"derived": {"article_count": 2}},
        }

        result = import_current(dry_run=True)

        self.assertEqual(result["status"], "dry_run")
        self.assertEqual(result["article_count"], 2)
        self.assertTrue(result["has_stats"])
        mock_client.get_payload.assert_called_once_with(force_refresh=True, snapshot_date=None)

    def test_postgres_news_client_returns_controller_bundle_shape(self):
        client = PostgresNewsClient(ttl_seconds=12)
        with patch.object(client, "_connect", return_value=_FakeConnection()):
            bundle = client.get_payload()

        self.assertEqual(bundle["source_mode"], "current")
        self.assertEqual(bundle["source_url"], "postgres://import")
        self.assertEqual(bundle["schema_version"], "1.0")
        self.assertEqual(bundle["contract"], "rss_pipeline_precomputed")
        self.assertEqual(bundle["ttl_seconds"], 12)
        self.assertEqual(bundle["input_articles_count"], 2)
        self.assertEqual(bundle["stats"]["total_articles"], 2)
        self.assertEqual([row["id"] for row in bundle["articles_normalized"]], ["a-newer", "a-older"])
        self.assertEqual(bundle["upstream_payload"]["source"], "postgres")

    def test_news_client_env_selector_defaults_to_json_and_can_select_postgres(self):
        with patch.dict("os.environ", {}, clear=True):
            self.assertIsInstance(_news_client_from_env(), RssDigestClient)
        with patch.dict("os.environ", {"NEWS_DATA_BACKEND": "postgres"}, clear=True):
            self.assertIsInstance(_news_client_from_env(), PostgresNewsClient)

    def test_json_and_postgres_controller_outputs_match_for_same_import_bundle(self):
        postgres_client = PostgresNewsClient(ttl_seconds=12)
        with patch.object(postgres_client, "_connect", return_value=_FakeConnection()):
            postgres_bundle = postgres_client.get_payload()

        json_controller = NewsController(_FakeJsonClient(postgres_bundle))
        with patch.object(postgres_client, "_connect", return_value=_FakeConnection()):
            postgres_controller = NewsController(postgres_client)

            json_digest = json_controller.get_digest(
                refresh=None,
                date=None,
                tag=None,
                source=None,
                limit="1",
                snapshot_date=None,
            )
            postgres_digest = postgres_controller.get_digest(
                refresh=None,
                date=None,
                tag=None,
                source=None,
                limit="1",
                snapshot_date=None,
            )
            self.assertEqual(json_digest.status_code, 200)
            self.assertEqual(postgres_digest.status_code, 200)
            self.assertEqual(json_digest.body["status"], postgres_digest.body["status"])
            self.assertEqual(json_digest.body["data"][0]["id"], postgres_digest.body["data"][0]["id"])
            self.assertEqual(json_digest.body["meta"]["returned_count"], postgres_digest.body["meta"]["returned_count"])

            json_stats = json_controller.get_stats(refresh=None, snapshot_date=None)
            postgres_stats = postgres_controller.get_stats(refresh=None, snapshot_date=None)
            self.assertEqual(json_stats.body["data"]["derived"], postgres_stats.body["data"]["derived"])


if __name__ == "__main__":
    unittest.main()
