import unittest

from src.pages.news_lens_correlations import _matrix_payload, _pair_rows, _select_lens_correlations


class NewsLensCorrelationsTests(unittest.TestCase):
    def test_select_lens_correlations_prefers_upstream(self):
        selected, source = _select_lens_correlations(
            {
                "analysis": {"lens_correlations": {"lenses": ["Evidence"], "correlation": {"raw": [[1.0]]}}},
                "derived": {"lens_correlations": {"lenses": ["Impact"], "correlation": {"raw": [[1.0]]}}},
            }
        )

        self.assertEqual(source, "upstream")
        self.assertEqual(selected.get("lenses"), ["Evidence"])

    def test_select_lens_correlations_falls_back_to_derived(self):
        selected, source = _select_lens_correlations(
            {
                "analysis": {"lens_correlations": {"lenses": []}},
                "derived": {"lens_correlations": {"lenses": ["Impact"], "correlation": {"raw": [[1.0]]}}},
            }
        )

        self.assertEqual(source, "derived")
        self.assertEqual(selected.get("lenses"), ["Impact"])

    def test_matrix_payload_normalizes_shape(self):
        lenses, matrix, label = _matrix_payload(
            {
                "lenses": ["Evidence", "Impact", "Novelty"],
                "correlation": {
                    "raw": [
                        [1.0, 0.2],
                        [0.2, 1.0, 0.1],
                    ]
                },
            },
            "corr_raw",
        )

        self.assertEqual(lenses, ["Evidence", "Impact", "Novelty"])
        self.assertEqual(label, "Correlation (Raw)")
        self.assertEqual(
            matrix,
            [
                [1.0, 0.2, None],
                [0.2, 1.0, 0.1],
                [None, None, None],
            ],
        )

    def test_pair_rows_sort_by_absolute_value_for_correlations(self):
        rows = _pair_rows(
            ["Evidence", "Impact", "Novelty"],
            [
                [1.0, 0.35, -0.85],
                [0.35, 1.0, 0.55],
                [-0.85, 0.55, 1.0],
            ],
            "corr_raw",
        )

        self.assertEqual(rows[0], ("Evidence", "Novelty", -0.85))
        self.assertEqual(rows[1], ("Impact", "Novelty", 0.55))
        self.assertEqual(rows[2], ("Evidence", "Impact", 0.35))

    def test_pair_rows_sort_by_descending_value_for_pairwise_counts(self):
        rows = _pair_rows(
            ["Evidence", "Impact", "Novelty"],
            [
                [10, 3, 8],
                [3, 9, 12],
                [8, 12, 11],
            ],
            "pairwise",
        )

        self.assertEqual(rows[0], ("Impact", "Novelty", 12.0))
        self.assertEqual(rows[1], ("Evidence", "Novelty", 8.0))
        self.assertEqual(rows[2], ("Evidence", "Impact", 3.0))


if __name__ == "__main__":
    unittest.main()
