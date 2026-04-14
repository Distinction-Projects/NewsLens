import unittest

import src.app  # noqa: F401
from src.pages.news_lenses import _select_lens_inventory


class NewsLensesTests(unittest.TestCase):
    def test_select_lens_inventory_prefers_derived(self):
        selected, source = _select_lens_inventory(
            {
                "analysis": {"lens_summary": {"lenses": [{"name": "Upstream"}]}},
                "derived": {"lens_inventory": {"lenses": [{"name": "Derived"}], "items_total": 5}},
            }
        )

        self.assertEqual(source, "derived")
        self.assertEqual(selected.get("lenses"), [{"name": "Derived"}])

    def test_select_lens_inventory_falls_back_to_upstream(self):
        selected, source = _select_lens_inventory(
            {
                "analysis": {"lens_summary": {"lenses": [{"name": "Upstream"}], "items_total": 3}},
                "derived": {},
            }
        )

        self.assertEqual(source, "upstream")
        self.assertEqual(selected.get("lenses"), [{"name": "Upstream"}])

    def test_select_lens_inventory_handles_missing(self):
        selected, source = _select_lens_inventory({"analysis": {}, "derived": {}})
        self.assertEqual(source, "missing")
        self.assertEqual(selected, {})


if __name__ == "__main__":
    unittest.main()
