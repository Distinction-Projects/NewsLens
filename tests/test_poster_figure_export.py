from __future__ import annotations

import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from src.analytics.export_poster_figures import (
    BUILDERS,
    FIGURE_PRESETS,
    NARRATIVE_POSTER_FIGURES,
    POSTER_FIGURES,
    SOURCE_TRIO,
    build_daily_lens_scores_reduced,
    build_discourse_constellation,
    build_event_plurality_panel,
    build_figure,
    build_lens_drift_dumbbell,
    build_lens_plurality_panel,
    build_source_lens_matrix,
    build_tag_lens_pca_clusters,
    build_topic_lens_divergence,
    build_two_tag_lens_comparison,
    build_two_tag_lens_fingerprints,
    figure_method_notes,
    filter_derived_for_sources,
    load_stats_payload,
    narrative_poster_sections,
    parse_source_filter,
    parse_tag_cluster_label_response,
    _plurality_article_weight,
    set_tag_cluster_label_overrides,
    semantic_tag_cluster_label,
    stats_derived,
    tag_cluster_fingerprint,
    tag_cluster_label_payload,
)


def _minimal_payload() -> dict:
    return {
        "status": "ok",
        "meta": {"generated_at": "2026-05-12T16:46:03Z"},
        "data": {
            "derived": {
                "source_lens_effects": {
                    "status": "ok",
                    "rows": [
                        {
                            "lens": "Lens A",
                            "eta_sq": 0.2,
                            "source_means": {"Source 1": 75.0, "Source 2": 55.0, "Fox News": 35.0},
                            "source_counts": {"Source 1": 4, "Source 2": 3, "Fox News": 2},
                            "significant_fdr_0_05": True,
                        },
                        {
                            "lens": "Lens B",
                            "eta_sq": 0.1,
                            "source_means": {"Source 1": 40.0, "Source 2": 70.0, "Fox News": 90.0},
                            "source_counts": {"Source 1": 4, "Source 2": 3, "Fox News": 2},
                            "significant_fdr_0_05": False,
                        },
                    ],
                }
            }
        },
    }


class PosterFigureExportTests(unittest.TestCase):
    def test_manifest_has_unique_ids_and_valid_builders(self):
        ids = [spec.id for spec in POSTER_FIGURES]
        self.assertEqual(len(ids), len(set(ids)))
        for spec in POSTER_FIGURES:
            self.assertIn(spec.builder, BUILDERS)
            self.assertGreater(spec.width, 0)
            self.assertGreater(spec.height, 0)
            self.assertTrue(spec.required_keys)

    def test_narrative_poster_preset_is_curated(self):
        self.assertIn("poster-narrative", FIGURE_PRESETS)
        specs = FIGURE_PRESETS["poster-narrative"]
        ids = [spec.id for spec in specs]
        self.assertEqual(len(ids), len(set(ids)))
        self.assertEqual(tuple(specs), NARRATIVE_POSTER_FIGURES)
        self.assertLess(len(specs), len(POSTER_FIGURES))
        self.assertNotIn("10_source_differentiation", ids)
        self.assertNotIn("14_article_volume_by_source", ids)
        for spec in specs:
            self.assertIn(spec.builder, BUILDERS)

    def test_narrative_captions_avoid_banned_phrases(self):
        banned = ["ranking media", "truth detection", "classifier performance", "objective analysis"]
        text = " ".join(f"{spec.title} {spec.caption}" for spec in NARRATIVE_POSTER_FIGURES).lower()
        for phrase in banned:
            self.assertNotIn(phrase, text)

    def test_stats_derived_accepts_public_stats_envelope(self):
        payload = _minimal_payload()
        derived = stats_derived(payload)
        self.assertIn("source_lens_effects", derived)

    def test_load_stats_payload_reads_local_json(self):
        payload = _minimal_payload()
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "stats.json"
            path.write_text(json.dumps(payload), encoding="utf-8")
            loaded = load_stats_payload(stats_json=path)
        self.assertEqual(loaded["status"], "ok")
        self.assertIn("source_lens_effects", loaded["data"]["derived"])

    def test_load_stats_payload_reads_url(self):
        payload = _minimal_payload()

        class FakeResponse(io.BytesIO):
            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb):
                return False

        response = FakeResponse(json.dumps(payload).encode("utf-8"))
        with patch("urllib.request.urlopen", return_value=response) as urlopen:
            loaded = load_stats_payload(stats_url="http://example.test/stats")
        urlopen.assert_called_once()
        self.assertEqual(loaded["status"], "ok")

    def test_missing_required_data_builds_placeholder(self):
        spec = POSTER_FIGURES[0]
        built = build_figure({}, spec)
        self.assertEqual(built.status, "unavailable")
        self.assertIn("Missing required derived keys", built.reason)
        self.assertTrue(built.figure.layout.title.text)

    def test_source_lens_matrix_builder_creates_heatmap(self):
        spec = POSTER_FIGURES[0]
        built = build_source_lens_matrix(_minimal_payload()["data"]["derived"], spec)
        self.assertEqual(built.status, "ok")
        self.assertEqual(built.figure.data[0].type, "heatmap")
        self.assertEqual(list(built.figure.data[0].y), ["Lens A", "Lens B"])
        self.assertEqual(list(built.figure.data[0].text[0]), ["75", "55", "35"])

    def test_tag_lens_pca_clusters_labels_cluster_annotations(self):
        spec = next(spec for spec in POSTER_FIGURES if spec.id == "06_tag_lens_pca_clusters")
        derived = {
            "tag_lens_pca": {
                "tag_points": [
                    {"tag": "Iran", "pc1": 1.0, "pc2": 0.5, "cluster": 1, "n_articles": 20},
                    {"tag": "Israel", "pc1": 1.2, "pc2": 0.7, "cluster": 1, "n_articles": 10},
                    {"tag": "AI", "pc1": -1.0, "pc2": -0.4, "cluster": 2, "n_articles": 12},
                    {"tag": "technology", "pc1": -1.1, "pc2": -0.5, "cluster": 2, "n_articles": 12},
                ]
            }
        }
        built = build_tag_lens_pca_clusters(derived, spec)
        annotation_text = [annotation.text for annotation in built.figure.layout.annotations]
        self.assertTrue(any(text.startswith("Security rhetoric / conflict<br>Iran, Israel<br>2 tags / 30 articles") for text in annotation_text))
        self.assertTrue(any(text.startswith("Technology governance<br>AI, technology<br>2 tags / 24 articles") for text in annotation_text))
        self.assertIn("Security rhetoric / conflict (2 tags)", [trace.name for trace in built.figure.data])
        self.assertIn("Technology governance (2 tags)", [trace.name for trace in built.figure.data])

    def test_semantic_tag_cluster_label_falls_back_to_top_tags(self):
        rows = [
            {"tag": "Rare Topic", "n_articles": 5},
            {"tag": "Another Topic", "n_articles": 3},
        ]
        self.assertEqual(semantic_tag_cluster_label(rows), "Rare Topic / Another Topic")

    def test_gpt_tag_cluster_label_payload_excludes_geometry(self):
        derived = {
            "tag_lens_pca": {
                "tag_points": [
                    {"tag": "human rights", "pc1": 1.5, "pc2": -2.2, "cluster": 1, "n_articles": 12},
                    {"tag": "government", "pc1": 1.8, "pc2": -2.0, "cluster": 1, "n_articles": 8},
                    {"tag": "sports", "pc1": -3.5, "pc2": 0.2, "cluster": 2, "n_articles": 20},
                ]
            }
        }
        payload = tag_cluster_label_payload(derived)
        serialized = json.dumps(payload)
        self.assertIn("Only tag labels and article counts", payload["input_policy"])
        self.assertIn("human rights", serialized)
        self.assertIn("n_articles", serialized)
        self.assertNotIn("pc1", serialized)
        self.assertNotIn("pc2", serialized)

    def test_gpt_tag_cluster_label_response_overrides_semantic_label(self):
        rows = [
            {"tag": "human rights", "n_articles": 12},
            {"tag": "government", "n_articles": 8},
        ]
        fingerprint = tag_cluster_fingerprint(rows)
        payload = {"clusters": [{"fingerprint": fingerprint, "tags": [{"tag": "human rights", "n_articles": 12}]}]}
        labels = parse_tag_cluster_label_response(
            json.dumps({"labels": [{"fingerprint": fingerprint, "label": "Rights and Governance"}]}),
            payload,
        )
        try:
            set_tag_cluster_label_overrides(labels)
            self.assertEqual(semantic_tag_cluster_label(rows), "Rights and Governance")
        finally:
            set_tag_cluster_label_overrides({})

    def test_lens_plurality_panel_builds_from_article_lens_rows(self):
        spec = next(spec for spec in POSTER_FIGURES if spec.id == "29_lens_plurality_panel")
        derived = {
            "lens_views": {
                "article_rows": [
                    {
                        "title": "Shared event becomes readable through multiple lenses",
                        "source": "Example News",
                        "published": "2026-05-15",
                        "lens_scores": {
                            "Agency and Voice Lens": 90,
                            "Authority and Source Positioning Lens": 20,
                            "Emotional Intensity Lens": 75,
                            "Causal Attribution Lens": 40,
                            "Omission and Silence Lens": 65,
                            "Objectivity vs Opinion Lens": 35,
                        },
                    }
                ]
            }
        }
        built = build_lens_plurality_panel(derived, spec)
        self.assertEqual(built.status, "ok")
        self.assertGreaterEqual(len(built.figure.layout.annotations), 7)
        self.assertLess(built.figure.layout.yaxis.range[0], 0)

    def test_lens_plurality_panel_selects_high_divergence_article(self):
        spec = next(spec for spec in POSTER_FIGURES if spec.id == "29_lens_plurality_panel")
        low_divergence = {
            "title": "Low divergence article",
            "source": "Example News",
            "published": "2026-05-15",
            "lens_scores": {lens: 50 for lens in [
                "Agency and Voice Lens",
                "Authority and Source Positioning Lens",
                "Emotional Intensity Lens",
                "Causal Attribution Lens",
                "Omission and Silence Lens",
                "Objectivity vs Opinion Lens",
            ]},
        }
        high_divergence = {
            "title": "High divergence article",
            "source": "Example News",
            "published": "2026-05-15",
            "lens_scores": {
                "Agency and Voice Lens": 100,
                "Authority and Source Positioning Lens": 5,
                "Emotional Intensity Lens": 80,
                "Causal Attribution Lens": 20,
                "Omission and Silence Lens": 70,
                "Objectivity vs Opinion Lens": 10,
            },
        }
        built = build_lens_plurality_panel({"lens_views": {"article_rows": [low_divergence, high_divergence]}}, spec)
        annotation_text = " ".join(str(annotation.text) for annotation in built.figure.layout.annotations)
        self.assertIn("High divergence article", annotation_text)

    def test_lens_plurality_panel_avoids_thin_live_stub(self):
        spec = next(spec for spec in POSTER_FIGURES if spec.id == "29_lens_plurality_panel")
        thin_live_stub = {
            "title": "WATCH LIVE: Thin article with maximal spread",
            "source": "Example News",
            "published": "2026-05-15",
            "lens_scores": {
                "Agency and Voice Lens": 100,
                "Authority and Source Positioning Lens": 5,
                "Emotional Intensity Lens": 80,
                "Causal Attribution Lens": 0,
                "Omission and Silence Lens": 70,
                "Objectivity vs Opinion Lens": 10,
            },
        }
        richer_article = {
            "title": "Online creators reshape a regional news ecosphere",
            "source": "Example News",
            "published": "2026-05-15",
            "lens_scores": {
                "Agency and Voice Lens": 90,
                "Authority and Source Positioning Lens": 75,
                "Emotional Intensity Lens": 20,
                "Causal Attribution Lens": 45,
                "Omission and Silence Lens": 80,
                "Objectivity vs Opinion Lens": 100,
            },
        }
        built = build_lens_plurality_panel({"lens_views": {"article_rows": [thin_live_stub, richer_article]}}, spec)
        annotation_text = " ".join(str(annotation.text) for annotation in built.figure.layout.annotations)
        self.assertIn("Online creators reshape", annotation_text)
        self.assertNotIn("WATCH LIVE", annotation_text)

    def test_plurality_article_weight_rejects_low_causality_live_item(self):
        weight, _title = _plurality_article_weight(
            {
                "title": "WATCH LIVE: Hegseth and Caine testify",
                "lens_scores": {
                    "Agency and Voice Lens": 50,
                    "Authority and Source Positioning Lens": 75,
                    "Emotional Intensity Lens": 5,
                    "Causal Attribution Lens": 0,
                    "Omission and Silence Lens": 90,
                    "Objectivity vs Opinion Lens": 100,
                },
            },
            list({
                "Agency and Voice Lens": None,
                "Authority and Source Positioning Lens": None,
                "Emotional Intensity Lens": None,
                "Causal Attribution Lens": None,
                "Omission and Silence Lens": None,
                "Objectivity vs Opinion Lens": None,
            }),
        )
        self.assertLess(weight, 0)

    def test_event_plurality_panel_builds_from_multisource_event(self):
        spec = next(spec for spec in NARRATIVE_POSTER_FIGURES if spec.id == "31_event_plurality_panel")
        derived = {
            "event_control": {
                "events": [
                    {
                        "representative_title": "Shared event across sources",
                        "date_start": "2026-05-01",
                        "date_end": "2026-05-02",
                        "article_count": 3,
                        "sources": ["A", "B", "C"],
                        "source_counts": {"A": 1, "B": 1, "C": 1},
                        "tag_counts": {"policy": 2, "conflict": 1},
                        "article_ids": ["1", "2", "3"],
                    }
                ]
            }
        }
        built = build_event_plurality_panel(derived, spec)
        self.assertEqual(built.status, "ok")
        annotation_text = " ".join(str(annotation.text) for annotation in built.figure.layout.annotations)
        self.assertIn("Shared event across sources", annotation_text)
        self.assertIn("Source spread", annotation_text)
        self.assertIn("shared coverage", annotation_text)
        self.assertIn("Inspectable trail", annotation_text)
        self.assertIn("source records", annotation_text)
        self.assertIn("traceable", annotation_text)
        self.assertNotIn("Embedding similarity", annotation_text)
        self.assertNotIn("event object", annotation_text)
        self.assertNotIn("Article IDs", annotation_text)

    def test_event_plurality_panel_handles_missing_event_data(self):
        spec = next(spec for spec in NARRATIVE_POSTER_FIGURES if spec.id == "31_event_plurality_panel")
        built = build_event_plurality_panel({"event_control": {"events": []}}, spec)
        self.assertEqual(built.status, "unavailable")
        self.assertIn("No multi-source event clusters", built.reason)

    def test_reduced_daily_lens_scores_limits_to_five_lenses(self):
        spec = next(spec for spec in NARRATIVE_POSTER_FIGURES if spec.id == "32_reduced_daily_lens_scores")
        derived = {
            "lens_time_series": {
                "series": [
                    {"lens": f"Lens {index}", "points": [{"date": "2026-05-01", "mean": index}]}
                    for index in range(10)
                ]
            }
        }
        built = build_daily_lens_scores_reduced(derived, spec)
        self.assertEqual(built.status, "ok")
        self.assertLessEqual(len(built.figure.data), 5)

    def test_two_tag_lens_comparison_compares_exactly_two_tags(self):
        spec = next(spec for spec in NARRATIVE_POSTER_FIGURES if spec.id == "33_two_tag_lens_comparison")
        derived = {
            "tag_sliced_analysis": {
                "tags": [
                    {
                        "tag": "Policy",
                        "n_articles": 12,
                        "lens_summary": {
                            "lenses": [
                                {"lens": "Agency and Voice Lens", "mean_percent": 80},
                                {"lens": "Objectivity vs Opinion Lens", "mean_percent": 60},
                            ]
                        },
                    },
                    {
                        "tag": "Conflict",
                        "n_articles": 9,
                        "lens_summary": {
                            "lenses": [
                                {"lens": "Agency and Voice Lens", "mean_percent": 40},
                                {"lens": "Objectivity vs Opinion Lens", "mean_percent": 90},
                            ]
                        },
                    },
                ]
            }
        }
        built = build_two_tag_lens_comparison(derived, spec)
        self.assertEqual(built.status, "ok")
        self.assertEqual(len(built.figure.data), 2)
        self.assertIn("Policy", built.figure.data[0].name)
        self.assertIn("Conflict", built.figure.data[1].name)

    def test_two_tag_selection_uses_pca_profiles_before_untagged_fallback(self):
        spec = next(spec for spec in NARRATIVE_POSTER_FIGURES if spec.id == "33_two_tag_lens_comparison")
        derived = {
            "tag_sliced_analysis": {
                "tags": [
                    {
                        "tag": "Untagged",
                        "n_articles": 100,
                        "lens_summary": {"lenses": [{"lens": "Agency and Voice Lens", "mean_percent": 20}]},
                    },
                    {
                        "tag": "world",
                        "n_articles": 20,
                        "lens_summary": {"lenses": [{"lens": "Agency and Voice Lens", "mean_percent": 30}]},
                    },
                ]
            },
            "tag_lens_pca": {
                "tag_points": [
                    {
                        "tag": "politics",
                        "n_articles": 50,
                        "lens_means": {
                            "Agency and Voice Lens": 80,
                            "Authority and Source Positioning Lens": 70,
                            "Emotional Intensity Lens": 30,
                        },
                    },
                    {
                        "tag": "sports",
                        "n_articles": 40,
                        "lens_means": {
                            "Agency and Voice Lens": 30,
                            "Authority and Source Positioning Lens": 45,
                            "Emotional Intensity Lens": 90,
                        },
                    },
                ]
            },
        }
        built = build_two_tag_lens_comparison(derived, spec)
        self.assertEqual(built.status, "ok")
        names = [trace.name for trace in built.figure.data]
        self.assertTrue(any("politics" in name for name in names))
        self.assertTrue(any("sports" in name for name in names))
        self.assertFalse(any("Untagged" in name for name in names))

    def test_two_tag_selection_prefers_visibly_separated_profiles(self):
        spec = next(spec for spec in NARRATIVE_POSTER_FIGURES if spec.id == "35_two_tag_lens_fingerprints")
        derived = {
            "tag_lens_pca": {
                "tag_points": [
                    {
                        "tag": "politics",
                        "n_articles": 100,
                        "lens_means": {
                            "Agency and Voice Lens": 70,
                            "Authority and Source Positioning Lens": 70,
                            "Emotional Intensity Lens": 40,
                            "Causal Attribution Lens": 50,
                            "Objectivity vs Opinion Lens": 90,
                        },
                    },
                    {
                        "tag": "policy",
                        "n_articles": 80,
                        "lens_means": {
                            "Agency and Voice Lens": 72,
                            "Authority and Source Positioning Lens": 71,
                            "Emotional Intensity Lens": 42,
                            "Causal Attribution Lens": 52,
                            "Objectivity vs Opinion Lens": 89,
                        },
                    },
                    {
                        "tag": "conflict",
                        "n_articles": 40,
                        "lens_means": {
                            "Agency and Voice Lens": 40,
                            "Authority and Source Positioning Lens": 50,
                            "Emotional Intensity Lens": 90,
                            "Causal Attribution Lens": 85,
                            "Objectivity vs Opinion Lens": 60,
                        },
                    },
                ]
            }
        }
        built = build_two_tag_lens_fingerprints(derived, spec)
        self.assertEqual(built.status, "ok")
        names = [trace.name for trace in built.figure.data]
        self.assertTrue(any("politics" in name for name in names))
        self.assertTrue(any("conflict" in name for name in names))
        self.assertFalse(any("policy" in name for name in names))

    def test_two_tag_lens_fingerprints_builds_radial_profiles(self):
        spec = next(spec for spec in NARRATIVE_POSTER_FIGURES if spec.id == "35_two_tag_lens_fingerprints")
        derived = {
            "tag_sliced_analysis": {
                "tags": [
                    {
                        "tag": "Policy",
                        "n_articles": 12,
                        "lens_summary": {
                            "lenses": [
                                {"lens": "Agency and Voice Lens", "mean_percent": 80},
                                {"lens": "Authority and Source Positioning Lens", "mean_percent": 65},
                                {"lens": "Emotional Intensity Lens", "mean_percent": 35},
                                {"lens": "Causal Attribution Lens", "mean_percent": 70},
                            ]
                        },
                    },
                    {
                        "tag": "Conflict",
                        "n_articles": 9,
                        "lens_summary": {
                            "lenses": [
                                {"lens": "Agency and Voice Lens", "mean_percent": 40},
                                {"lens": "Authority and Source Positioning Lens", "mean_percent": 55},
                                {"lens": "Emotional Intensity Lens", "mean_percent": 90},
                                {"lens": "Causal Attribution Lens", "mean_percent": 85},
                            ]
                        },
                    },
                ]
            }
        }
        built = build_two_tag_lens_fingerprints(derived, spec)
        self.assertEqual(built.status, "ok")
        self.assertEqual(len(built.figure.data), 2)
        self.assertEqual(built.figure.data[0].type, "scatterpolar")
        self.assertIn("Policy", built.figure.data[0].name)
        self.assertIn("Conflict", built.figure.data[1].name)
        self.assertLessEqual(len(built.figure.data[0].theta), 7)

    def test_discourse_constellation_uses_semantic_formation_labels(self):
        spec = next(spec for spec in NARRATIVE_POSTER_FIGURES if spec.id == "34_discourse_constellation")
        derived = {
            "tag_lens_pca": {
                "tag_points": [
                    {"tag": "Iran", "pc1": 1.0, "pc2": 0.5, "n_articles": 20},
                    {"tag": "Israel", "pc1": 1.2, "pc2": 0.7, "n_articles": 10},
                    {"tag": "AI", "pc1": -1.0, "pc2": -0.4, "n_articles": 12},
                    {"tag": "technology", "pc1": -1.1, "pc2": -0.5, "n_articles": 12},
                ]
            }
        }
        built = build_discourse_constellation(derived, spec)
        self.assertEqual(built.status, "ok")
        trace_names = [trace.name for trace in built.figure.data]
        self.assertIn("Security rhetoric / conflict", trace_names)
        self.assertIn("Technology governance", trace_names)
        annotation_text = " ".join(str(annotation.text) for annotation in built.figure.layout.annotations)
        self.assertNotIn("not fixed taxonomies", annotation_text)
        self.assertEqual(built.figure.layout.xaxis.title.text, "PC1")
        self.assertEqual(built.figure.layout.yaxis.title.text, "PC2")

    def test_lens_drift_dumbbell_uses_baseline_and_recent_markers(self):
        spec = next(spec for spec in NARRATIVE_POSTER_FIGURES if spec.id == "36_lens_drift_dumbbell")
        derived = {
            "drift_diagnostics": {
                "lens_drift": [
                    {
                        "lens": "Emotional Intensity Lens",
                        "baseline_mean": 50,
                        "recent_mean": 65,
                        "delta": 15,
                    },
                    {
                        "lens": "Objectivity vs Opinion Lens",
                        "baseline_mean": 80,
                        "recent_mean": 72,
                        "delta": -8,
                    },
                ]
            }
        }
        built = build_lens_drift_dumbbell(derived, spec)
        self.assertEqual(built.status, "ok")
        self.assertIn("Baseline", [trace.name for trace in built.figure.data])
        self.assertIn("Recent", [trace.name for trace in built.figure.data])
        self.assertTrue(any(annotation.text == "+15.0" for annotation in built.figure.layout.annotations))

    def test_narrative_poster_sections_include_core_claim_and_order(self):
        manifest = {
            "figures": [
                {
                    "id": spec.id,
                    "title": spec.title,
                    "caption": spec.caption,
                    "method": figure_method_notes(spec)["method"],
                    "encoding": figure_method_notes(spec)["encoding"],
                    "interpretive_note": figure_method_notes(spec)["interpretive_note"],
                    "svg": f"svg/{spec.id}.svg",
                }
                for spec in NARRATIVE_POSTER_FIGURES
            ]
        }
        text = narrative_poster_sections(manifest)
        self.assertIn("Core Claim", text)
        self.assertIn("navigational infrastructure for interpretive inquiry", text)
        self.assertIn("Inspectable Multi-Lens Reading", text)
        self.assertIn("Two Tag Readings Across Lenses", text)
        self.assertIn("Discursive Formation Constellation", text)
        self.assertIn("Two Tag Lens Fingerprints", text)
        self.assertIn("Lens Drift: Baseline to Recent", text)
        self.assertIn("Method:", text)
        self.assertIn("Encoding:", text)
        self.assertIn("Interpretive note:", text)

    def test_figure_method_notes_cover_narrative_figures(self):
        for spec in NARRATIVE_POSTER_FIGURES:
            notes = figure_method_notes(spec)
            self.assertTrue(notes["method"])
            self.assertTrue(notes["encoding"])
            self.assertTrue(notes["interpretive_note"])
        divergence = next(spec for spec in NARRATIVE_POSTER_FIGURES if spec.id == "30_topic_lens_divergence")
        notes = figure_method_notes(divergence)
        self.assertIn("Rows are topic or tag slices", notes["encoding"])
        self.assertIn("not better or worse", notes["interpretive_note"])

    def test_topic_lens_divergence_builds_topic_heatmap(self):
        spec = next(spec for spec in POSTER_FIGURES if spec.id == "30_topic_lens_divergence")
        derived = {
            "lens_views": {
                "stability_rows": [
                    {"lens": "Agency and Voice Lens", "mean": 50},
                    {"lens": "Authority and Source Positioning Lens", "mean": 55},
                    {"lens": "Emotional Intensity Lens", "mean": 60},
                    {"lens": "Causal Attribution Lens", "mean": 45},
                    {"lens": "Omission and Silence Lens", "mean": 40},
                    {"lens": "Objectivity vs Opinion Lens", "mean": 70},
                ]
            },
            "source_topic_control": {
                "topics": [
                    {
                        "topic": "Policy",
                        "n_articles": 10,
                        "source_lens_effects": {
                            "rows": [
                                {
                                    "lens": "Agency and Voice Lens",
                                    "source_means": {"A": 70, "B": 50},
                                    "source_counts": {"A": 3, "B": 7},
                                },
                                {
                                    "lens": "Authority and Source Positioning Lens",
                                    "source_means": {"A": 75, "B": 55},
                                    "source_counts": {"A": 3, "B": 7},
                                },
                                {
                                    "lens": "Emotional Intensity Lens",
                                    "source_means": {"A": 80, "B": 60},
                                    "source_counts": {"A": 3, "B": 7},
                                },
                                {
                                    "lens": "Causal Attribution Lens",
                                    "source_means": {"A": 65, "B": 45},
                                    "source_counts": {"A": 3, "B": 7},
                                },
                                {
                                    "lens": "Omission and Silence Lens",
                                    "source_means": {"A": 50, "B": 40},
                                    "source_counts": {"A": 3, "B": 7},
                                },
                                {
                                    "lens": "Objectivity vs Opinion Lens",
                                    "source_means": {"A": 40, "B": 60},
                                    "source_counts": {"A": 3, "B": 7},
                                },
                            ]
                        },
                    }
                ]
            },
        }
        built = build_topic_lens_divergence(derived, spec)
        self.assertEqual(built.status, "ok")
        self.assertEqual(built.figure.data[0].type, "heatmap")
        self.assertEqual(
            list(built.figure.data[0].x),
            ["Agency<br>Voice", "Authority", "Emotion", "Causality", "Omission", "Objectivity"],
        )
        self.assertNotIn("Overall<br>divergence", list(built.figure.data[0].x))
        annotation_text = "\n".join(str(annotation.text) for annotation in built.figure.layout.annotations)
        self.assertIn("Who acts or speaks?", annotation_text)
        self.assertIn("Positive cells mean stronger rubric agreement", annotation_text)

    def test_source_filter_limits_matrix_and_preserves_requested_order(self):
        derived = _minimal_payload()["data"]["derived"]
        filtered = filter_derived_for_sources(derived, ("Fox News", "Source 1"))
        built = build_source_lens_matrix(filtered, POSTER_FIGURES[0])
        self.assertEqual(list(built.figure.data[0].x), ["Fox News<br>n=2", "Source 1<br>n=4"])
        self.assertEqual(list(built.figure.data[0].z[0]), [35.0, 75.0])

    def test_source_trio_matrix_preset_is_single_compact_figure(self):
        specs = FIGURE_PRESETS["source-trio-matrix"]
        self.assertEqual(len(specs), 1)
        self.assertLess(specs[0].width, POSTER_FIGURES[0].width)
        self.assertLess(specs[0].height, POSTER_FIGURES[0].height)
        self.assertEqual(SOURCE_TRIO, ("Al Jazeera", "NPR", "Fox News"))

    def test_parse_source_filter_splits_comma_list(self):
        self.assertEqual(parse_source_filter("Al Jazeera, NPR, Fox News"), SOURCE_TRIO)


if __name__ == "__main__":
    unittest.main()
