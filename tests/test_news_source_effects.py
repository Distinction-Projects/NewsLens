import unittest

import src.app  # noqa: F401
from src.pages.news_source_effects import (
    _effects_figure,
    _reliability_status_parts,
    _results_table,
    _select_source_effects_view,
    _select_source_reliability_view,
    _topic_options,
)


class NewsSourceEffectsTests(unittest.TestCase):
    def test_topic_options_include_article_counts(self):
        options = _topic_options(
            [
                {"topic": "Policy", "n_articles": 8},
                {"topic": "Untagged", "n_articles": 2},
            ]
        )
        self.assertEqual(
            options,
            [
                {"label": "Policy (n=8)", "value": "Policy"},
                {"label": "Untagged (n=2)", "value": "Untagged"},
            ],
        )

    def test_select_source_effects_view_switches_between_pooled_and_topic_slice(self):
        data = {
            "derived": {
                "source_lens_effects": {"status": "ok", "rows": [{"lens": "Evidence", "eta_sq": 0.22}]},
                "source_topic_control": {
                    "topics": [
                        {
                            "topic": "Policy",
                            "n_articles": 6,
                            "source_lens_effects": {"status": "ok", "rows": [{"lens": "Evidence", "eta_sq": 0.08}]},
                        },
                        {
                            "topic": "Untagged",
                            "n_articles": 2,
                            "source_lens_effects": {
                                "status": "unavailable",
                                "reason": "Insufficient source coverage for one-way lens tests.",
                                "rows": [],
                            },
                        },
                    ]
                },
            }
        }

        pooled_effects, pooled_scope, pooled_options, pooled_topic, pooled_disabled = _select_source_effects_view(
            data, "pooled", None
        )
        self.assertEqual(pooled_effects["status"], "ok")
        self.assertIn("topic-confounded", pooled_scope)
        self.assertEqual(pooled_topic, "Policy")
        self.assertTrue(pooled_disabled)
        self.assertEqual(len(pooled_options), 2)

        topic_effects, topic_scope, topic_options, topic_value, topic_disabled = _select_source_effects_view(
            data, "within_topic", "Policy"
        )
        self.assertEqual(topic_effects["status"], "ok")
        self.assertIn("within-topic (Policy)", topic_scope)
        self.assertEqual(topic_value, "Policy")
        self.assertFalse(topic_disabled)
        self.assertEqual(len(topic_options), 2)

    def test_unavailable_topic_slice_does_not_break_visual_helpers(self):
        data = {
            "derived": {
                "source_lens_effects": {"status": "ok", "rows": [{"lens": "Evidence", "eta_sq": 0.22}]},
                "source_topic_control": {
                    "topics": [
                        {
                            "topic": "Untagged",
                            "n_articles": 2,
                            "source_lens_effects": {
                                "status": "unavailable",
                                "reason": "Insufficient source coverage for one-way lens tests.",
                                "rows": [],
                            },
                        }
                    ]
                },
            }
        }

        topic_effects, _scope, _options, _value, _disabled = _select_source_effects_view(
            data, "within_topic", "Untagged"
        )
        self.assertEqual(topic_effects["status"], "unavailable")
        self.assertIn("Insufficient source coverage", topic_effects["reason"])

        figure = _effects_figure([])
        table = _results_table([])
        self.assertIsNotNone(figure)
        self.assertIsNotNone(table)

    def test_select_source_reliability_view_tracks_mode_and_topic(self):
        data = {
            "derived": {
                "source_reliability": {
                    "pooled": {"status": "ok", "tier": "moderate", "score": 0.58, "flags": []},
                    "topics": [
                        {
                            "topic": "Policy",
                            "assessment": {"status": "ok", "tier": "high", "score": 0.79, "flags": []},
                        },
                        {
                            "topic": "Untagged",
                            "assessment": {"status": "unavailable", "tier": "unavailable", "score": None, "flags": []},
                        },
                    ],
                }
            }
        }

        pooled = _select_source_reliability_view(data, "pooled", None)
        self.assertEqual(pooled["tier"], "moderate")

        topic = _select_source_reliability_view(data, "within_topic", "Policy")
        self.assertEqual(topic["tier"], "high")

        fallback = _select_source_reliability_view(data, "within_topic", "Missing")
        self.assertEqual(fallback["tier"], "moderate")

    def test_reliability_status_parts_formats_without_score(self):
        parts = _reliability_status_parts({"status": "unavailable", "tier": "unavailable", "score": None, "flags": []})
        self.assertIn("Reliability: unavailable", parts)
        self.assertIn("Reliability status: unavailable", parts)


if __name__ == "__main__":
    unittest.main()
