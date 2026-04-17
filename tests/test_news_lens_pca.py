import unittest

import src.app  # noqa: F401
from src.pages.news_lens_pca import (
    _mds_scatter_figure,
    _select_lens_mds,
    _select_lens_pca,
    _select_lens_separation,
    _variance_driver_figure,
)


class NewsLensPcaTests(unittest.TestCase):
    def test_select_lens_pca_prefers_derived(self):
        payload, source = _select_lens_pca(
            {
                "derived": {"lens_pca": {"status": "ok", "components": ["PC1"]}},
                "analysis": {"lens_pca": {"status": "legacy"}},
            }
        )

        self.assertEqual(source, "derived")
        self.assertEqual(payload.get("status"), "ok")
        self.assertEqual(payload.get("components"), ["PC1"])

    def test_select_lens_pca_missing_returns_empty(self):
        payload, source = _select_lens_pca({"derived": {}, "analysis": {}})

        self.assertEqual(source, "missing")
        self.assertEqual(payload, {})

    def test_select_lens_mds_prefers_derived(self):
        payload, source = _select_lens_mds(
            {
                "derived": {"lens_mds": {"status": "ok", "dimensions": ["MDS1", "MDS2"]}},
                "analysis": {"lens_mds": {"status": "legacy"}},
            }
        )

        self.assertEqual(source, "derived")
        self.assertEqual(payload.get("status"), "ok")
        self.assertEqual(payload.get("dimensions"), ["MDS1", "MDS2"])

    def test_select_lens_separation_prefers_derived(self):
        payload, source = _select_lens_separation(
            {
                "derived": {"lens_separation": {"status": "ok", "separation_ratio": 1.5}},
                "analysis": {"lens_separation": {"status": "legacy"}},
            }
        )

        self.assertEqual(source, "derived")
        self.assertEqual(payload.get("status"), "ok")
        self.assertEqual(payload.get("separation_ratio"), 1.5)

    def test_mds_scatter_figure_renders_points_and_centroids(self):
        figure = _mds_scatter_figure(
            {
                "article_points": [
                    {
                        "title": "Article A",
                        "source": "Source A",
                        "strongest_lens": "Evidence",
                        "mds1": 0.4,
                        "mds2": -0.2,
                    },
                    {
                        "title": "Article B",
                        "source": "Source B",
                        "strongest_lens": "Impact",
                        "mds1": -0.5,
                        "mds2": 0.3,
                    },
                ],
                "source_centroids": [
                    {"source": "Source A", "mds1": 0.4, "mds2": -0.2},
                    {"source": "Source B", "mds1": -0.5, "mds2": 0.3},
                ],
                "stress": 0.123,
            },
            color_by="source",
            max_points=300,
        )

        self.assertGreaterEqual(len(figure.data), 3)
        self.assertIn("Stress: 0.123", str(figure.layout.title.text))

    def test_variance_driver_figure_uses_weighted_contributions(self):
        figure = _variance_driver_figure(
            {
                "variance_drivers": [
                    {"lens": "Evidence", "weighted_contribution": 0.4},
                    {"lens": "Impact", "weighted_contribution": 0.35},
                    {"lens": "Novelty", "weighted_contribution": 0.25},
                ]
            },
            top_n=3,
        )

        self.assertEqual(len(figure.data), 1)
        self.assertEqual(list(figure.data[0]["x"]), ["Evidence", "Impact", "Novelty"])
        self.assertAlmostEqual(sum(figure.data[0]["y"]), 100.0, places=6)


if __name__ == "__main__":
    unittest.main()
