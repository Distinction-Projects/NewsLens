import unittest

import src.app  # noqa: F401
from src.pages.news_source_differentiation import _select_source_differentiation


class NewsSourceDifferentiationTests(unittest.TestCase):
    def test_select_source_differentiation_prefers_derived(self):
        selected, source = _select_source_differentiation(
            {
                "analysis": {"source_differentiation": {"status": "upstream"}},
                "derived": {"source_differentiation": {"status": "derived"}},
            }
        )

        self.assertEqual(source, "derived")
        self.assertEqual(selected.get("status"), "derived")

    def test_select_source_differentiation_falls_back_to_upstream(self):
        selected, source = _select_source_differentiation(
            {
                "analysis": {"source_differentiation": {"status": "upstream"}},
                "derived": {},
            }
        )

        self.assertEqual(source, "upstream")
        self.assertEqual(selected.get("status"), "upstream")

    def test_select_source_differentiation_handles_missing(self):
        selected, source = _select_source_differentiation({"analysis": {}, "derived": {}})
        self.assertEqual(source, "missing")
        self.assertEqual(selected, {})


if __name__ == "__main__":
    unittest.main()
