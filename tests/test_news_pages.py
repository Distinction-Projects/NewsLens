import unittest

from src.app import server


class NewsPageRouteTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = server.test_client()

    def test_news_digest_page_route(self):
        response = self.client.get("/news/digest")
        self.assertEqual(response.status_code, 200)
        self.assertIn("text/html", response.content_type)

    def test_news_stats_page_route(self):
        response = self.client.get("/news/stats")
        self.assertEqual(response.status_code, 200)
        self.assertIn("text/html", response.content_type)

    def test_news_integration_page_route(self):
        response = self.client.get("/news/integration")
        self.assertEqual(response.status_code, 200)
        self.assertIn("text/html", response.content_type)

    def test_news_scraped_page_route(self):
        response = self.client.get("/news/scraped")
        self.assertEqual(response.status_code, 200)
        self.assertIn("text/html", response.content_type)

    def test_news_trends_page_route(self):
        response = self.client.get("/news/trends")
        self.assertEqual(response.status_code, 200)
        self.assertIn("text/html", response.content_type)

    def test_news_sources_page_route(self):
        response = self.client.get("/news/sources")
        self.assertEqual(response.status_code, 200)
        self.assertIn("text/html", response.content_type)

    def test_news_lenses_page_route(self):
        response = self.client.get("/news/lenses")
        self.assertEqual(response.status_code, 200)
        self.assertIn("text/html", response.content_type)

    def test_news_lens_matrix_page_route(self):
        response = self.client.get("/news/lens-matrix")
        self.assertEqual(response.status_code, 200)
        self.assertIn("text/html", response.content_type)

    def test_news_lens_correlations_page_route(self):
        response = self.client.get("/news/lens-correlations")
        self.assertEqual(response.status_code, 200)
        self.assertIn("text/html", response.content_type)

    def test_news_source_differentiation_page_route(self):
        response = self.client.get("/news/source-differentiation")
        self.assertEqual(response.status_code, 200)
        self.assertIn("text/html", response.content_type)

    def test_news_source_effects_page_route(self):
        response = self.client.get("/news/source-effects")
        self.assertEqual(response.status_code, 200)
        self.assertIn("text/html", response.content_type)

    def test_news_tags_page_route(self):
        response = self.client.get("/news/tags")
        self.assertEqual(response.status_code, 200)
        self.assertIn("text/html", response.content_type)

    def test_news_score_lab_page_route(self):
        response = self.client.get("/news/score-lab")
        self.assertEqual(response.status_code, 200)
        self.assertIn("text/html", response.content_type)

    def test_news_raw_json_page_route(self):
        response = self.client.get("/news/raw-json")
        self.assertEqual(response.status_code, 200)
        self.assertIn("text/html", response.content_type)

    def test_news_lens_explorer_page_route(self):
        response = self.client.get("/news/lens-explorer")
        self.assertEqual(response.status_code, 200)
        self.assertIn("text/html", response.content_type)

    def test_news_lens_by_source_page_route(self):
        response = self.client.get("/news/lens-by-source")
        self.assertEqual(response.status_code, 200)
        self.assertIn("text/html", response.content_type)

    def test_news_lens_stability_page_route(self):
        response = self.client.get("/news/lens-stability")
        self.assertEqual(response.status_code, 200)
        self.assertIn("text/html", response.content_type)

    def test_news_source_tag_matrix_page_route(self):
        response = self.client.get("/news/source-tag-matrix")
        self.assertEqual(response.status_code, 200)
        self.assertIn("text/html", response.content_type)

    def test_news_data_quality_page_route(self):
        response = self.client.get("/news/data-quality")
        self.assertEqual(response.status_code, 200)
        self.assertIn("text/html", response.content_type)

if __name__ == "__main__":
    unittest.main()
