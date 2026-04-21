import unittest

import dash
import dash_bootstrap_components as dbc
from dash import html

import src.app  # noqa: F401
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

    def test_news_lens_pca_page_route(self):
        response = self.client.get("/news/lens-pca")
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


def _iter_components(node):
    if node is None:
        return
    if isinstance(node, (str, int, float, bool)):
        return
    yield node
    children = getattr(node, "children", None)
    if isinstance(children, (list, tuple)):
        for child in children:
            yield from _iter_components(child)
    elif children is not None:
        yield from _iter_components(children)


def _has_h3(node):
    return any(isinstance(component, html.H3) for component in _iter_components(node))


def _has_intro_class(node):
    for component in _iter_components(node):
        class_name = getattr(component, "className", None)
        if isinstance(class_name, str) and "news-page-intro" in class_name.split():
            return True
    return False


def _find_intro_accordions(node):
    accordions = []
    for component in _iter_components(node):
        if isinstance(component, dbc.Accordion):
            class_name = getattr(component, "className", None)
            if isinstance(class_name, str) and "news-page-intro" in class_name.split():
                accordions.append(component)
    return accordions


class NewsPageIntroLayoutTests(unittest.TestCase):
    def test_every_news_page_has_single_intro_directly_after_title_row(self):
        news_pages = []
        for page in dash.page_registry.values():
            path = page.get("path")
            if isinstance(path, str) and path.startswith("/news/"):
                news_pages.append((path, page.get("module")))

        self.assertGreater(len(news_pages), 0)

        for path, module_name in news_pages:
            with self.subTest(path=path, module=module_name):
                module = __import__(module_name, fromlist=["layout"])
                layout = module.layout() if callable(module.layout) else module.layout
                children = list(layout.children) if isinstance(layout.children, (list, tuple)) else [layout.children]

                title_indexes = [idx for idx, child in enumerate(children) if _has_h3(child)]
                intro_indexes = [idx for idx, child in enumerate(children) if _has_intro_class(child)]

                self.assertGreaterEqual(len(title_indexes), 1)
                self.assertEqual(len(intro_indexes), 1)
                self.assertEqual(intro_indexes[0], title_indexes[0] + 1)

                intro_accordions = _find_intro_accordions(children[intro_indexes[0]])
                self.assertEqual(len(intro_accordions), 1)
                self.assertTrue(getattr(intro_accordions[0], "start_collapsed", False))


if __name__ == "__main__":
    unittest.main()
