import unittest

import src.app  # noqa: F401
from src.pages.news_lens_pca import (
    _mds_scatter_figure,
    _select_lens_mds,
    _select_lens_pca,
    _select_lens_separation,
    _temporal_diagnostics_figure,
    _temporal_embedding_figure,
    _temporal_slider_config,
    _select_lens_temporal_embedding,
    _select_lens_temporal_embedding_mds,
    _select_lens_time_series,
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

    def test_select_lens_time_series_prefers_derived(self):
        payload, source = _select_lens_time_series(
            {
                "derived": {"lens_time_series": {"status": "ok", "dates": ["2026-03-01"]}},
                "analysis": {"lens_time_series": {"status": "legacy"}},
            }
        )

        self.assertEqual(source, "derived")
        self.assertEqual(payload.get("status"), "ok")
        self.assertEqual(payload.get("dates"), ["2026-03-01"])

    def test_select_lens_temporal_embedding_prefers_derived(self):
        payload, source = _select_lens_temporal_embedding(
            {
                "derived": {"lens_temporal_embedding": {"status": "ok", "points": []}},
                "analysis": {"lens_temporal_embedding": {"status": "legacy"}},
            }
        )

        self.assertEqual(source, "derived")
        self.assertEqual(payload.get("status"), "ok")
        self.assertEqual(payload.get("points"), [])

    def test_select_lens_temporal_embedding_mds_prefers_derived(self):
        payload, source = _select_lens_temporal_embedding_mds(
            {
                "derived": {"lens_temporal_embedding_mds": {"status": "ok", "points": []}},
                "analysis": {"lens_temporal_embedding_mds": {"status": "legacy"}},
            }
        )

        self.assertEqual(source, "derived")
        self.assertEqual(payload.get("status"), "ok")
        self.assertEqual(payload.get("points"), [])

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

    def test_temporal_slider_config_uses_day_centroids(self):
        slider_max, slider_marks, slider_value, slider_step = _temporal_slider_config(
            {
                "day_centroids": [
                    {"day_index": 0, "date": "2026-04-01"},
                    {"day_index": 2, "date": "2026-04-03"},
                ]
            },
            {"day_centroids": [{"day_index": 1, "date": "2026-04-02"}]},
            requested_value=None,
            is_playing=False,
            play_tick=0,
        )

        self.assertEqual(slider_max, 2)
        self.assertEqual(slider_value, 2)
        self.assertEqual(slider_step, 1)
        self.assertIn(0, slider_marks)
        self.assertIn(1, slider_marks)
        self.assertIn(2, slider_marks)

    def test_temporal_embedding_figure_filters_by_day_index(self):
        figure = _temporal_embedding_figure(
            {
                "status": "ok",
                "points": [
                    {"pc1": 0.1, "pc2": 0.2, "day_index": 0, "title": "A", "source": "S1", "date": "2026-04-01"},
                    {"pc1": 0.3, "pc2": 0.4, "day_index": 2, "title": "B", "source": "S2", "date": "2026-04-03"},
                ],
                "day_centroids": [
                    {"pc1": 0.1, "pc2": 0.2, "day_index": 0, "date": "2026-04-01"},
                    {"pc1": 0.3, "pc2": 0.4, "day_index": 2, "date": "2026-04-03"},
                ],
            },
            max_day_index=0,
        )

        self.assertGreaterEqual(len(figure.data), 1)
        self.assertEqual(len(figure.data[0]["x"]), 1)

    def test_temporal_slider_config_applies_weekly_step_in_playback(self):
        slider_max, _slider_marks, slider_value, slider_step = _temporal_slider_config(
            {
                "day_centroids": [
                    {"day_index": 0, "date": "2026-04-01"},
                    {"day_index": 7, "date": "2026-04-08"},
                    {"day_index": 14, "date": "2026-04-15"},
                ]
            },
            {},
            requested_value=None,
            is_playing=True,
            play_tick=1,
            step_size=7,
        )

        self.assertEqual(slider_max, 14)
        self.assertEqual(slider_value, 7)
        self.assertEqual(slider_step, 7)

    def test_temporal_embedding_figure_applies_trailing_window(self):
        figure = _temporal_embedding_figure(
            {
                "status": "ok",
                "points": [
                    {"pc1": 0.1, "pc2": 0.2, "day_index": 1, "title": "A", "source": "S1", "date": "2026-04-01"},
                    {"pc1": 0.3, "pc2": 0.4, "day_index": 5, "title": "B", "source": "S2", "date": "2026-04-05"},
                ],
                "day_centroids": [
                    {"pc1": 0.1, "pc2": 0.2, "day_index": 1, "date": "2026-04-01"},
                    {"pc1": 0.3, "pc2": 0.4, "day_index": 5, "date": "2026-04-05"},
                ],
            },
            max_day_index=5,
            trailing_window_days=2,
        )

        self.assertGreaterEqual(len(figure.data), 1)
        self.assertEqual(len(figure.data[0]["x"]), 1)

    def test_temporal_diagnostics_figure_renders_volume_and_drift(self):
        figure = _temporal_diagnostics_figure(
            {
                "status": "ok",
                "points": [
                    {"day_index": 0, "date": "2026-04-01"},
                    {"day_index": 1, "date": "2026-04-02"},
                    {"day_index": 1, "date": "2026-04-02"},
                ],
                "day_centroids": [
                    {"pc1": 0.1, "pc2": 0.2, "day_index": 0, "date": "2026-04-01"},
                    {"pc1": 0.4, "pc2": 0.6, "day_index": 1, "date": "2026-04-02"},
                ],
            },
            {
                "status": "ok",
                "day_centroids": [
                    {"mds1": 0.2, "mds2": 0.1, "day_index": 0, "date": "2026-04-01"},
                    {"mds1": 0.6, "mds2": 0.4, "day_index": 1, "date": "2026-04-02"},
                ],
            },
            max_day_index=1,
        )

        self.assertGreaterEqual(len(figure.data), 3)
        self.assertEqual(list(figure.data[0]["y"]), [1, 2])

    def test_temporal_diagnostics_figure_applies_trailing_window(self):
        figure = _temporal_diagnostics_figure(
            {
                "status": "ok",
                "points": [
                    {"day_index": 0, "date": "2026-04-01"},
                    {"day_index": 3, "date": "2026-04-04"},
                ],
                "day_centroids": [
                    {"pc1": 0.1, "pc2": 0.2, "day_index": 0, "date": "2026-04-01"},
                    {"pc1": 0.3, "pc2": 0.4, "day_index": 3, "date": "2026-04-04"},
                ],
            },
            {"status": "missing"},
            max_day_index=3,
            trailing_window_days=1,
        )

        self.assertGreaterEqual(len(figure.data), 2)
        self.assertEqual(list(figure.data[0]["x"]), ["2026-04-04"])


if __name__ == "__main__":
    unittest.main()
