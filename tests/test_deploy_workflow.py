import unittest
from pathlib import Path


WORKFLOW = Path(__file__).resolve().parents[1] / ".github/workflows/deploy-droplet.yml"


class DeploymentWorkflowTests(unittest.TestCase):
    def test_sync_preserves_generated_snapshot_and_embedding_cache(self):
        workflow = WORKFLOW.read_text(encoding="utf-8")
        sync = workflow.split("- name: Sync App To Droplet", 1)[1].split("- name:", 1)[0]
        self.assertIn("--exclude 'data/cache/'", sync)
        self.assertIn("--exclude 'data/processed/'", sync)

    def test_smoke_requires_real_precomputed_stats_and_fresh_upstream(self):
        workflow = WORKFLOW.read_text(encoding="utf-8")
        self.assertIn('meta.get("stats_backend") != "precomputed"', workflow)
        self.assertIn('meta.get("stats_backend_fallback")', workflow)
        self.assertIn('freshness.get("is_fresh") is not True', workflow)
        self.assertIn("/health/news-freshness", workflow)

    def test_snapshot_is_generated_before_api_restart(self):
        workflow = WORKFLOW.read_text(encoding="utf-8")
        self.assertLess(
            workflow.index("-m src.analytics.build_news_snapshot"),
            workflow.index("systemctl restart newslens-api"),
        )

    def test_daily_deploy_follows_the_rss_publication_window(self):
        workflow = WORKFLOW.read_text(encoding="utf-8")
        self.assertIn('cron: "17 14 * * *"', workflow)
        self.assertIn("timeout-minutes: 30", workflow)


if __name__ == "__main__":
    unittest.main()
