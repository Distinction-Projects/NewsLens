import unittest

import src.app  # noqa: F401
from src.pages.news_source_differentiation import (
    _reliability_status_parts,
    _select_source_differentiation,
    _select_source_differentiation_view,
    _select_source_reliability_view,
    _topic_options,
)


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

    def test_select_source_differentiation_view_switches_modes(self):
        data = {
            "derived": {
                "source_differentiation": {"status": "ok", "reason": "", "source_counts": {"A": 3, "B": 3}},
                "source_topic_control": {
                    "topics": [
                        {
                            "topic": "Policy",
                            "n_articles": 6,
                            "source_differentiation": {
                                "status": "ok",
                                "reason": "",
                                "source_counts": {"A": 3, "B": 3},
                            },
                        },
                        {
                            "topic": "Untagged",
                            "n_articles": 2,
                            "source_differentiation": {
                                "status": "unavailable",
                                "reason": "Need at least 2 sources with complete rows.",
                                "source_counts": {"A": 2},
                            },
                        },
                    ]
                },
            }
        }

        pooled_view, pooled_source, pooled_scope, pooled_options, pooled_topic, pooled_disabled = (
            _select_source_differentiation_view(data, "pooled", None)
        )
        self.assertEqual(pooled_source, "derived")
        self.assertEqual(pooled_view["status"], "ok")
        self.assertIn("topic-confounded", pooled_scope)
        self.assertTrue(pooled_disabled)
        self.assertEqual(pooled_topic, "Policy")
        self.assertEqual(len(pooled_options), 2)

        topic_view, topic_source, topic_scope, topic_options, topic_value, topic_disabled = _select_source_differentiation_view(
            data, "within_topic", "Policy"
        )
        self.assertEqual(topic_source, "derived-topic-slice")
        self.assertEqual(topic_view["status"], "ok")
        self.assertIn("within-topic (Policy)", topic_scope)
        self.assertFalse(topic_disabled)
        self.assertEqual(topic_value, "Policy")
        self.assertEqual(len(topic_options), 2)

    def test_select_source_differentiation_view_handles_unavailable_slice(self):
        data = {
            "derived": {
                "source_differentiation": {"status": "ok"},
                "source_topic_control": {
                    "topics": [
                        {
                            "topic": "Untagged",
                            "n_articles": 2,
                            "source_differentiation": {
                                "status": "unavailable",
                                "reason": "Need at least 2 sources with complete rows.",
                                "source_counts": {"A": 2},
                            },
                        }
                    ]
                },
            }
        }
        topic_view, _topic_source, _topic_scope, _options, _value, _disabled = _select_source_differentiation_view(
            data, "within_topic", "Untagged"
        )
        self.assertEqual(topic_view["status"], "unavailable")
        self.assertIn("Need at least 2 sources", topic_view["reason"])

    def test_select_source_reliability_view_tracks_mode_and_topic(self):
        data = {
            "derived": {
                "source_reliability": {
                    "pooled": {"status": "ok", "tier": "low", "score": 0.31, "flags": ["low_article_count"]},
                    "topics": [
                        {
                            "topic": "Policy",
                            "assessment": {"status": "ok", "tier": "high", "score": 0.82, "flags": []},
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
        self.assertEqual(pooled["tier"], "low")

        topic = _select_source_reliability_view(data, "within_topic", "Policy")
        self.assertEqual(topic["tier"], "high")

        fallback = _select_source_reliability_view(data, "within_topic", "Missing")
        self.assertEqual(fallback["tier"], "low")

    def test_reliability_status_parts_formats_score_and_flags(self):
        parts = _reliability_status_parts({"status": "ok", "tier": "moderate", "score": 0.57, "flags": ["a", "b"]})
        self.assertIn("Reliability: moderate (0.57)", parts)
        self.assertIn("Reliability status: ok", parts)
        self.assertIn("Reliability flags: 2", parts)


if __name__ == "__main__":
    unittest.main()
