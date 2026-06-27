from __future__ import annotations

import argparse
import ast
import hashlib
import json
import math
import os
import tempfile
import urllib.request
from collections import defaultdict
from dataclasses import dataclass, replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

import plotly.graph_objects as go
import plotly.io as pio

try:
    pio.kaleido.scope.mathjax = None
except Exception:
    pass


DEFAULT_STATS_URL = "http://64.23.250.112/api/news/stats"
DEFAULT_OUTPUT_DIR = Path("data/exports/poster_figures")
DEFAULT_WIDTH = 1400
DEFAULT_HEIGHT = 900
DENSE_WIDTH = 1600
DENSE_HEIGHT = 1000
COMPACT_WIDTH = 1000
COMPACT_HEIGHT = 650
SOURCE_TRIO = ("Al Jazeera", "NPR", "Fox News")
MAX_POSTER_TAG_CLUSTERS = 6
DEFAULT_TAG_CLUSTER_LABEL_MODEL = os.environ.get("NEWS_TAG_CLUSTER_LABEL_MODEL", "gpt-4o")
TAG_CLUSTER_LABEL_OVERRIDES: dict[str, str] = {}

PALETTE = [
    "#0f766e",
    "#2563eb",
    "#f97316",
    "#7c3aed",
    "#16a34a",
    "#dc2626",
    "#ca8a04",
    "#0891b2",
    "#be185d",
    "#4f46e5",
    "#65a30d",
    "#9333ea",
]

HIGH_CONTRAST_HEATMAP_COLORSCALE = [
    [0.0, "#08306b"],
    [0.2, "#08519c"],
    [0.4, "#2171b5"],
    [0.6, "#b2182b"],
    [0.8, "#8b0000"],
    [1.0, "#4a0000"],
]

LENS_SCORE_HEATMAP_COLORSCALE = [
    [0.0, "#3b0764"],
    [0.2, "#6b21a8"],
    [0.4, "#7e22ce"],
    [0.6, "#047857"],
    [0.8, "#166534"],
    [1.0, "#052e16"],
]

TAG_INTENSITY_HEATMAP_COLORSCALE = [
    [0.0, "#fff7ed"],
    [0.18, "#fed7aa"],
    [0.36, "#fdba74"],
    [0.55, "#fb923c"],
    [0.75, "#ea580c"],
    [1.0, "#7c2d12"],
]

TAG_SEMANTIC_LABELS = (
    (
        "Security rhetoric / conflict",
        (
            "iran",
            "israel",
            "gaza",
            "palestine",
            "lebanon",
            "syria",
            "yemen",
            "middle east",
            "hormuz",
            "ceasefire",
            "hamas",
            "hostage",
            "war",
            "conflict",
            "military",
            "diplomacy",
            "security",
        ),
    ),
    (
        "Institutional legitimacy",
        (
            "trump",
            "white house",
            "election",
            "elections",
            "politics",
            "congress",
            "supreme court",
            "redistricting",
            "legal",
            "investigation",
            "u.s.",
            "us",
        ),
    ),
    ("Public health risk", ("health", "hantavirus", "disease", "covid", "vaccine", "science", "medicine")),
    ("Economic anxiety", ("economy", "business", "markets", "tariff", "trade", "inflation", "jobs", "banking")),
    ("Crime / public safety", ("crime", "shooting", "police", "court", "criminal", "violence")),
    ("Technology governance", ("ai", "technology", "tech", "openai", "artificial intelligence", "cyber", "data")),
    ("Cultural attention", ("sports", "culture", "entertainment", "film", "music")),
    ("Mobility / infrastructure", ("aviation", "cruise", "ship", "travel", "transport")),
    ("Diplomatic geopolitics", ("china", "russia", "uk", "australia", "europe", "global", "foreign")),
)

LENS_PLURALITY_RUBRICS = {
    "Agency and Voice Lens": "Who is granted action, responsibility, or voice?",
    "Authority and Source Positioning Lens": "Which institutions or sources become authoritative?",
    "Emotional Intensity Lens": "How strongly does affect organize the account?",
    "Causal Attribution Lens": "How are causes, blame, and consequence assigned?",
    "Omission and Silence Lens": "What absences or unspoken contexts become visible?",
    "Objectivity vs Opinion Lens": "How much does the prose perform neutrality or stance?",
}

LENS_READING_PROMPTS = {
    "Agency and Voice Lens": "Reading cue: locate who acts, speaks, or is acted upon.",
    "Authority and Source Positioning Lens": "Reading cue: identify who becomes credible or official.",
    "Emotional Intensity Lens": "Reading cue: track how affect organizes attention.",
    "Causal Attribution Lens": "Reading cue: follow how causes and consequences are assigned.",
    "Omission and Silence Lens": "Reading cue: ask what context remains absent or muted.",
    "Objectivity vs Opinion Lens": "Reading cue: examine how neutrality or stance is performed.",
}

LENS_POSTER_CUES = {
    "Agency and Voice Lens": "Who acts or speaks?",
    "Authority and Source Positioning Lens": "Who becomes credible?",
    "Emotional Intensity Lens": "How does affect organize attention?",
    "Causal Attribution Lens": "How is cause assigned?",
    "Omission and Silence Lens": "What remains absent?",
    "Objectivity vs Opinion Lens": "How is neutrality performed?",
}

PLURALITY_TITLE_REJECT_TERMS = (
    "watch live",
    "live /",
    "this week on",
    "photos:",
    "video:",
    "cnn founder",
)

PLURALITY_TITLE_DOWNRANK_TERMS = (
    "sunday morning",
    "died at",
    "dies aged",
    "football",
    "olympic",
    "mcelroy",
    "mourinho",
    "benfica",
    "beehive",
    "counting underway",
)

PLURALITY_TITLE_PREFERRED_TERMS = (
    "news ecosphere",
    "online creators",
    "reshaping",
    "tribe",
    "farmland",
    "human rights",
    "migration",
    "tariff",
    "ceasefire",
    "iran",
    "gaza",
    "government",
    "policy",
    "economy",
    "conflict",
)


@dataclass(frozen=True)
class FigureSpec:
    id: str
    title: str
    caption: str
    required_keys: tuple[str, ...]
    builder: str
    width: int = DEFAULT_WIDTH
    height: int = DEFAULT_HEIGHT
    show_title: bool = True


@dataclass
class BuiltFigure:
    figure: go.Figure
    caption: str
    status: str = "ok"
    reason: str = ""


Builder = Callable[[dict[str, Any], FigureSpec], BuiltFigure]


POSTER_FIGURES: tuple[FigureSpec, ...] = (
    FigureSpec(
        id="01_source_lens_matrix",
        title="Source-Lens Annotation Matrix",
        caption="Mean annotation values are shown for each source across the interpretive lenses. This pooled view describes corpus-level source patterns and should be paired with topic, tag, or event controls before making comparative claims.",
        required_keys=("source_lens_effects",),
        builder="source_lens_matrix",
        width=DENSE_WIDTH,
        height=DENSE_HEIGHT,
    ),
    FigureSpec(
        id="02_lens_correlation_heatmap",
        title="Lens Overlap and Independence",
        caption="Pairwise correlations show which lens annotations tend to move together across articles and which lenses preserve distinct interpretive dimensions.",
        required_keys=("lens_correlations",),
        builder="lens_correlation_heatmap",
        width=DENSE_WIDTH,
        height=DENSE_HEIGHT,
    ),
    FigureSpec(
        id="03_lens_pca_variance",
        title="Latent Lens Structure",
        caption="Explained variance summarizes how much of the corpus-level lens variation is captured by each exploratory component, indicating whether a small number of dimensions organize the annotation space.",
        required_keys=("lens_pca",),
        builder="lens_pca_variance",
    ),
    FigureSpec(
        id="04_article_pca_source_space",
        title="Article Space by Source",
        caption="Each point represents an article projected from its multi-lens annotation profile; source centroids provide descriptive anchors for comparing article organization without ranking outlets.",
        required_keys=("lens_pca",),
        builder="article_pca_source_space",
    ),
    FigureSpec(
        id="05_article_mds_source_space",
        title="Distance-Preserving Article Space",
        caption="Article lens profiles are arranged so nearby points have similar annotation patterns, offering a distance-preserving map for comparative reading rather than a single interpretive outcome.",
        required_keys=("lens_mds",),
        builder="article_mds_source_space",
    ),
    FigureSpec(
        id="06_tag_lens_pca_clusters",
        title="Tag Formations in Lens Space",
        caption="Tags are positioned by their average lens profiles and grouped into named discursive formations, making tag-level rhetorical organization readable at a glance.",
        required_keys=("tag_lens_pca",),
        builder="tag_lens_pca_clusters",
    ),
    FigureSpec(
        id="07_group_latent_source_centroids",
        title="Source Centroids in Lens Space",
        caption="Source centroids summarize each outlet's aggregate position in lens-profile space, with marker size indicating the number of analyzed articles.",
        required_keys=("group_latent_space",),
        builder="group_latent_source_centroids",
    ),
    FigureSpec(
        id="08_tag_momentum",
        title="Temporal Attention Momentum",
        caption="Decay-weighted momentum identifies tags whose recent attention is rising relative to their baseline presence; the index combines recency and recent-window lift, not overall popularity.",
        required_keys=("tag_momentum",),
        builder="tag_momentum",
    ),
    FigureSpec(
        id="09_temporal_centroid_path",
        title="Corpus Movement Over Time",
        caption="Daily corpus centroids trace how aggregate annotation patterns move through lens space over time, with marker size indicating article volume on each date.",
        required_keys=("lens_temporal_embedding",),
        builder="temporal_centroid_path",
    ),
    FigureSpec(
        id="10_source_differentiation",
        title="Pooled Source Separability",
        caption="Pooled source separability is compared with a majority-source baseline to show whether lens profiles distinguish sources; this view is topic-confounded and does not measure source quality.",
        required_keys=("source_differentiation",),
        builder="source_differentiation",
    ),
    FigureSpec(
        id="11_source_effects_by_lens",
        title="Pooled Source Effects by Lens",
        caption="Lens-level source effect sizes summarize where pooled source differences are largest, with significance status shown where available; controlled slices are needed for interpretation.",
        required_keys=("source_lens_effects",),
        builder="source_effects_by_lens",
    ),
    FigureSpec(
        id="12_event_control_summary",
        title="Same-Event Comparison Coverage",
        caption="Multi-source event clusters identify shared story contexts where source comparisons can be made while holding the covered event more nearly constant.",
        required_keys=("event_control",),
        builder="event_control_summary",
    ),
    FigureSpec(
        id="13_controlled_analysis_coverage",
        title="Controlled Comparison Coverage",
        caption="This coverage summary shows how many topic, tag, and event slices meet the data requirements for controlled source comparison.",
        required_keys=("source_topic_control", "tag_sliced_analysis", "event_control"),
        builder="controlled_analysis_coverage",
    ),
    FigureSpec(
        id="14_article_volume_by_source",
        title="Corpus Coverage by Source",
        caption="Article counts by source describe the corpus composition and provide necessary context for interpreting source-level comparisons.",
        required_keys=("source_counts",),
        builder="article_volume_by_source",
    ),
    FigureSpec(
        id="15_top_tags",
        title="Most Common Tags",
        caption="The most frequent tags summarize topical composition in the corpus and contextualize later source, lens, and temporal comparisons.",
        required_keys=("tag_counts",),
        builder="top_tags",
    ),
    FigureSpec(
        id="16_source_tag_intensity",
        title="Source-Tag Composition",
        caption="Tag intensity is normalized within each source, showing which high-frequency tags occupy a larger or smaller share of each source's coverage.",
        required_keys=("chart_aggregates",),
        builder="source_tag_intensity",
        width=1100,
        height=720,
    ),
    FigureSpec(
        id="17_score_status_counts",
        title="Annotation Coverage",
        caption="Annotation status counts show how many articles are scored, zero-valued, or unusable, providing data-quality context for downstream analysis.",
        required_keys=("score_status",),
        builder="score_status_counts",
    ),
    FigureSpec(
        id="18_score_status_by_source",
        title="Annotation Coverage by Source",
        caption="Per-source annotation coverage shows whether missing or unusable records are unevenly distributed across outlets.",
        required_keys=("chart_aggregates",),
        builder="score_status_by_source",
    ),
    FigureSpec(
        id="19_daily_article_counts",
        title="Daily Corpus Volume",
        caption="Daily article counts show the collection volume over time and help separate discourse movement from changes in corpus size.",
        required_keys=("daily_counts_utc",),
        builder="daily_article_counts",
    ),
    FigureSpec(
        id="20_publish_hour_distribution",
        title="Publication Timing",
        caption="Publication-hour distribution shows when articles enter the corpus in UTC, supporting interpretation of temporal coverage patterns.",
        required_keys=("chart_aggregates",),
        builder="publish_hour_distribution",
    ),
    FigureSpec(
        id="21_dominant_lens_frequency",
        title="Strongest Lens by Article",
        caption="This count shows which lens has the highest annotation value within each article profile; it is a profile summary, not a claim that one lens dominates meaning.",
        required_keys=("lens_views",),
        builder="dominant_lens_frequency",
    ),
    FigureSpec(
        id="22_lens_mean_vs_stddev",
        title="Lens Mean and Variability",
        caption="Mean and standard deviation are plotted for each lens to show which interpretive dimensions are consistently high and which vary most across articles.",
        required_keys=("lens_views",),
        builder="lens_mean_vs_stddev",
    ),
    FigureSpec(
        id="23_pca_stability",
        title="Latent Component Stability",
        caption="Bootstrap and subsample stability estimates indicate whether exploratory latent components remain consistent when the article set changes.",
        required_keys=("latent_space_stability",),
        builder="pca_stability",
    ),
    FigureSpec(
        id="24_pca_loading_variability",
        title="Variable Lens Loadings",
        caption="The most variable lens loadings identify which lenses contribute least consistently to resampled latent-space components.",
        required_keys=("latent_space_stability",),
        builder="pca_loading_variability",
    ),
    FigureSpec(
        id="25_daily_lens_scores",
        title="Daily Lens Annotation Values",
        caption="Daily mean annotation values trace how selected lenses change over time across the corpus.",
        required_keys=("lens_time_series",),
        builder="daily_lens_scores",
    ),
    FigureSpec(
        id="26_lens_drift",
        title="Lens Movement: Recent Minus Baseline",
        caption="Recent-window means are subtracted from baseline-window means to show which lens annotations increased or decreased most over time.",
        required_keys=("drift_diagnostics",),
        builder="lens_drift",
    ),
    FigureSpec(
        id="27_distribution_share_shifts",
        title="Source and Tag Share Movement",
        caption="Recent-vs-baseline share changes show which sources and tags occupy more or less of the corpus in the recent window.",
        required_keys=("drift_diagnostics",),
        builder="distribution_share_shifts",
    ),
    FigureSpec(
        id="28_focus_lens_source_means",
        title="Highest-Effect Lens by Source",
        caption="For the lens with the strongest pooled source effect, source means show where annotation values differ most; this remains descriptive and topic-confounded.",
        required_keys=("source_lens_effects",),
        builder="focus_lens_source_means",
    ),
    FigureSpec(
        id="29_lens_plurality_panel",
        title="One Event, Multiple Interpretive Readings",
        caption="One article is placed at the center and surrounded by selected lens readings, showing how a single discourse object can be organized through multiple rubric-mediated interpretations.",
        required_keys=("lens_views",),
        builder="lens_plurality_panel",
        width=1500,
        height=950,
    ),
    FigureSpec(
        id="30_topic_lens_divergence",
        title="Interpretive Divergence Across Topics",
        caption="Selected topic and tag slices are compared with corpus lens averages; color marks where a slice shows stronger or weaker rubric agreement than the corpus baseline.",
        required_keys=("source_topic_control", "lens_views"),
        builder="topic_lens_divergence",
        width=DENSE_WIDTH,
        height=950,
    ),
)

SOURCE_TRIO_MATRIX_FIGURES: tuple[FigureSpec, ...] = (
    replace(
        POSTER_FIGURES[0],
        id="01_source_lens_matrix_aljazeera_npr_fox",
        title="Lens Scores: Al Jazeera, NPR, and Fox News",
        caption=(
            "Mean annotation values are shown for three selected news organizations across the interpretive lenses. "
            "The compact pooled view is useful for poster comparison but remains topic-confounded."
        ),
        width=COMPACT_WIDTH,
        height=700,
    ),
)

NARRATIVE_POSTER_FIGURES: tuple[FigureSpec, ...] = (
    replace(
        POSTER_FIGURES[28],
        title="Inspectable Multi-Lens Reading",
        caption="One article is represented as an inspectable annotation object: article metadata remains in the center while surrounding lenses show distinct rubric-mediated readings.",
        width=1700,
        height=1125,
        show_title=False,
    ),
    FigureSpec(
        id="31_event_plurality_panel",
        title="Comparative Event Reading Surface",
        caption="A multi-source event cluster is treated as a shared comparison unit, with surrounding context summarizing source spread, rhetorical tags, coverage window, and traceability.",
        required_keys=("event_control",),
        builder="event_plurality_panel",
        width=1700,
        height=1050,
        show_title=False,
    ),
    replace(
        POSTER_FIGURES[1],
        title="Analytical Pluralism Across Lenses",
        caption="Lens correlations identify which interpretive annotations overlap across articles and which dimensions remain comparatively independent.",
        width=1500,
        height=950,
        show_title=False,
    ),
    replace(
        POSTER_FIGURES[5],
        title="Lens-Mediated Discourse Patterns",
        caption="Tags are positioned by similarity in their average lens profiles, then grouped with interpretive formation labels that summarize nearby rhetorical patterns.",
        width=1500,
        height=950,
        show_title=False,
    ),
    FigureSpec(
        id="34_discourse_constellation",
        title="Discursive Formation Constellation",
        caption="Tag groups are displayed as a labeled constellation of discursive formations, emphasizing rhetorical organization rather than raw geometric projection.",
        required_keys=("tag_lens_pca",),
        builder="discourse_constellation",
        width=1600,
        height=1000,
        show_title=False,
    ),
    replace(
        POSTER_FIGURES[29],
        title="Interpretive Divergence Across Lenses",
        caption="Topic and tag slices are compared against corpus lens averages to show which discourse areas activate particular interpretive lenses more or less strongly.",
        width=1700,
        height=1100,
        show_title=False,
    ),
    FigureSpec(
        id="33_two_tag_lens_comparison",
        title="Two Tag Readings Across Lenses",
        caption="Two tag-defined discourse slices are compared lens by lens, making differences in annotation intensity visible for each interpretive question.",
        required_keys=("tag_sliced_analysis",),
        builder="two_tag_lens_comparison",
        width=1500,
        height=900,
        show_title=False,
    ),
    FigureSpec(
        id="35_two_tag_lens_fingerprints",
        title="Two Tag Lens Fingerprints",
        caption="Two tag-defined discourse slices are shown as radial lens profiles; differences in polygon shape indicate which interpretive dimensions are more strongly activated by each tag.",
        required_keys=("tag_sliced_analysis",),
        builder="two_tag_lens_fingerprints",
        width=1400,
        height=950,
        show_title=False,
    ),
    replace(
        POSTER_FIGURES[7],
        title="Temporal Attention Movement",
        caption="Decay-weighted tag momentum highlights discourse objects whose recent attention is rising relative to baseline presence; the measure is temporal movement, not popularity.",
        width=1200,
        height=720,
        show_title=False,
    ),
    FigureSpec(
        id="36_lens_drift_dumbbell",
        title="Lens Drift: Baseline to Recent",
        caption="Baseline and recent annotation means are connected for each lens, making directional movement across interpretive dimensions visible over time.",
        required_keys=("drift_diagnostics",),
        builder="lens_drift_dumbbell",
        width=1450,
        height=900,
        show_title=False,
    ),
    replace(
        POSTER_FIGURES[25],
        title="Temporal Movement in Computational Annotation",
        caption="Recent-minus-baseline lens shifts summarize how corpus-level annotation patterns changed between the comparison windows.",
        width=1300,
        height=850,
        show_title=False,
    ),
    FigureSpec(
        id="32_reduced_daily_lens_scores",
        title="Selected Lens Movement Within a Tag",
        caption="Daily mean lens values are shown for a single tag slice, tying temporal movement to one discourse object rather than the full corpus.",
        required_keys=("group_temporal_latent_space",),
        builder="daily_lens_scores_reduced",
        width=1500,
        height=900,
        show_title=False,
    ),
)

FIGURE_PRESETS: dict[str, tuple[FigureSpec, ...]] = {
    "poster": POSTER_FIGURES,
    "poster-narrative": NARRATIVE_POSTER_FIGURES,
    "source-trio-matrix": SOURCE_TRIO_MATRIX_FIGURES,
}


def _as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _as_dict_or_literal(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    if isinstance(value, str) and value.strip().startswith("{"):
        try:
            parsed = ast.literal_eval(value)
        except (SyntaxError, ValueError):
            return {}
        return parsed if isinstance(parsed, dict) else {}
    return {}


def _as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _num(value: Any, default: float | None = None) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return default
    if not math.isfinite(number):
        return default
    return number


def _short_label(value: Any, max_len: int = 28) -> str:
    text = str(value or "Unknown")
    if len(text) <= max_len:
        return text
    clipped = text[:max_len].rsplit(" ", 1)[0].strip()
    return clipped or text[:max_len].strip()


def _wrap_text(value: Any, width: int = 34, max_lines: int = 3) -> str:
    words = str(value or "").split()
    lines: list[str] = []
    current: list[str] = []
    for word in words:
        candidate = " ".join(current + [word])
        if current and len(candidate) > width:
            lines.append(" ".join(current))
            current = [word]
        else:
            current.append(word)
        if len(lines) >= max_lines:
            break
    if current and len(lines) < max_lines:
        lines.append(" ".join(current))
    return "<br>".join(lines)


def _quote_wrapped_question(value: Any, width: int = 26, max_lines: int = 2) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    wrapped = _wrap_text(text, width=width, max_lines=max_lines)
    lines = wrapped.split("<br>") if wrapped else [text]
    if len(lines) == 1:
        return f'"{lines[0]}"'
    lines[0] = f'"{lines[0]}'
    lines[-1] = f'{lines[-1]}"'
    return "<br>".join(lines)


LENS_LABELS = {
    "Agency and Voice Lens": "Agency / Voice",
    "Authority and Source Positioning Lens": "Authority",
    "Causal Attribution Lens": "Causality",
    "Credibility Lens": "Credibility",
    "Emotional Intensity Lens": "Emotion",
    "Entity-Level Sentiment Lens": "Entity Sentiment",
    "Epistemic Modality and Certainty Lens": "Certainty",
    "Hegemonic Common-Sense Lens": "Common Sense",
    "Linguistic Quality Lens": "Language Quality",
    "Objectivity vs Opinion Lens": "Objectivity",
    "Omission and Silence Lens": "Omission",
    "Sentiment Clarity Lens": "Sentiment Clarity",
}


INTERPRETABLE_DIVERGENCE_LENSES: tuple[tuple[str, str], ...] = (
    ("Agency and Voice Lens", "Who acts or speaks?"),
    ("Authority and Source Positioning Lens", "Whose sources count?"),
    ("Emotional Intensity Lens", "How affective is the language?"),
    ("Causal Attribution Lens", "How are causes assigned?"),
    ("Omission and Silence Lens", "What context remains absent?"),
    ("Objectivity vs Opinion Lens", "Reportage or argument?"),
)


FIGURE_METHOD_NOTES: dict[str, dict[str, str]] = {
    "01_source_lens_matrix": {
        "method": "Heatmap of source-by-lens mean annotation values.",
        "encoding": "Rows are interpretive lenses; columns are sources; color and cell labels show mean annotation value.",
        "interpretive_note": "Use as a descriptive reading surface, not as a source ranking.",
    },
    "01_source_lens_matrix_aljazeera_npr_fox": {
        "method": "Compact heatmap of source-by-lens mean annotation values for three selected outlets.",
        "encoding": "Rows are interpretive lenses; columns are selected sources; color and cell labels show mean annotation value.",
        "interpretive_note": "Use only as a compact poster comparison; pooled source views remain topic-confounded.",
    },
    "02_lens_correlation_heatmap": {
        "method": "Pairwise Pearson correlation matrix across lens annotation values.",
        "encoding": "Rows and columns are lenses; color shows whether lens values move together or apart.",
        "interpretive_note": "Useful for showing which lenses overlap and which preserve distinct interpretive dimensions.",
    },
    "03_lens_pca_variance": {
        "method": "Explained-variance summary from principal component analysis of article lens profiles.",
        "encoding": "X-axis lists latent components; y-axis shows percent variance explained.",
        "interpretive_note": "Use only as an exploratory geometry check, not as a claim that components are natural categories.",
    },
    "04_article_pca_source_space": {
        "method": "Article lens profiles projected into two PCA dimensions with source centroids.",
        "encoding": "Each point is an article; centroid markers summarize source locations in the projected lens space.",
        "interpretive_note": "Use to show navigable structure in annotations, not source quality.",
    },
    "05_article_mds_source_space": {
        "method": "Distance-preserving multidimensional scaling of article lens profiles.",
        "encoding": "Nearby points have more similar multi-lens annotation profiles; source centroids provide orientation.",
        "interpretive_note": "Use as a similarity map for comparative reading.",
    },
    "06_tag_lens_pca_clusters": {
        "method": "Tag mean lens profiles projected into a two-dimensional formation map and grouped by nearby patterns.",
        "encoding": "Each point is a tag; color groups tags into named discourse formations; marker size reflects article count.",
        "interpretive_note": "Formation names are interpretive summaries of annotation patterns, not fixed taxonomies.",
    },
    "07_group_latent_source_centroids": {
        "method": "Source centroids in group-level lens-profile space.",
        "encoding": "Points summarize sources; marker size reflects analyzed article count.",
        "interpretive_note": "Use as a corpus map, not as a source leaderboard.",
    },
    "08_tag_momentum": {
        "method": "Decay-weighted temporal momentum for tag attention.",
        "encoding": "X-axis shows momentum index; y-axis lists tags; bars combine recency with recent-vs-baseline lift.",
        "interpretive_note": "Use as temporal attention movement, not popularity ranking.",
    },
    "09_temporal_centroid_path": {
        "method": "Daily corpus centroid path through lens-profile space.",
        "encoding": "Points are days; connecting lines show movement over time; marker size reflects article volume.",
        "interpretive_note": "Use to show temporal movement in annotation patterns.",
    },
    "10_source_differentiation": {
        "method": "Pooled source-separability estimate compared with a majority-source baseline.",
        "encoding": "Bars compare separability accuracy to baseline accuracy.",
        "interpretive_note": "This is topic-confounded unless paired with controlled views.",
    },
    "11_source_effects_by_lens": {
        "method": "Lens-level source effect-size summary with statistical-significance status.",
        "encoding": "X-axis shows effect size; y-axis lists lenses; color marks FDR status where available.",
        "interpretive_note": "Use as orientation before topic, tag, or event controls.",
    },
    "12_event_control_summary": {
        "method": "Event-controlled coverage summary for multi-source event clusters.",
        "encoding": "Bars summarize article/event counts and comparable event coverage.",
        "interpretive_note": "Supports comparison within shared story contexts.",
    },
    "13_controlled_analysis_coverage": {
        "method": "Availability summary for controlled comparison slices.",
        "encoding": "Grouped bars count available topic, tag, and event slices.",
        "interpretive_note": "Use to show where controlled analysis is possible.",
    },
    "14_article_volume_by_source": {
        "method": "Article-count distribution by source.",
        "encoding": "X-axis shows article count; y-axis lists sources.",
        "interpretive_note": "Use only as corpus-composition context.",
    },
    "15_top_tags": {
        "method": "Frequency count of corpus tags.",
        "encoding": "X-axis shows article count; y-axis lists tags.",
        "interpretive_note": "Use as tag-composition context.",
    },
    "16_source_tag_intensity": {
        "method": "Source-normalized tag-share heatmap.",
        "encoding": "Rows are tags; columns are sources; color shows each tag's share within a source's articles.",
        "interpretive_note": "Normalizing by source volume helps show composition rather than raw article count.",
    },
    "17_score_status_counts": {
        "method": "Data-quality status count chart.",
        "encoding": "Bars count annotated, zero, and unusable articles.",
        "interpretive_note": "Use as audit context only.",
    },
    "18_score_status_by_source": {
        "method": "Stacked data-quality counts by source.",
        "encoding": "X-axis lists sources; stacked colors count scored and unusable records.",
        "interpretive_note": "Use to expose uneven annotation coverage.",
    },
    "19_daily_article_counts": {
        "method": "Daily article-count time series.",
        "encoding": "X-axis is date; y-axis is article count.",
        "interpretive_note": "Use as corpus-volume context.",
    },
    "20_publish_hour_distribution": {
        "method": "Publish-hour histogram.",
        "encoding": "X-axis is UTC hour; y-axis is article count.",
        "interpretive_note": "Use for temporal collection context.",
    },
    "21_dominant_lens_frequency": {
        "method": "Frequency of strongest article-level lens.",
        "encoding": "Bars count how often each lens is the maximum annotation value for an article.",
        "interpretive_note": "Use cautiously because strongest-lens frequency can imply false dominance.",
    },
    "22_lens_mean_vs_stddev": {
        "method": "Lens mean-versus-variability scatterplot.",
        "encoding": "X-axis is mean annotation value; y-axis is standard deviation.",
        "interpretive_note": "Use to identify lenses that vary most across the corpus.",
    },
    "23_pca_stability": {
        "method": "Bootstrap/subsample stability diagnostic for latent components.",
        "encoding": "Y-axis shows mean component similarity across resampling.",
        "interpretive_note": "Use to decide whether latent-space interpretation is stable enough to discuss.",
    },
    "24_pca_loading_variability": {
        "method": "Loading-variability diagnostic across resampled latent-space runs.",
        "encoding": "X-axis shows maximum loading variability; y-axis lists lenses.",
        "interpretive_note": "Higher variability means a lens contributes less stably to latent axes.",
    },
    "25_daily_lens_scores": {
        "method": "Daily mean annotation trajectories for selected lenses.",
        "encoding": "X-axis is date; y-axis is mean annotation value.",
        "interpretive_note": "Use only when reduced to a readable set of lenses.",
    },
    "26_lens_drift": {
        "method": "Recent-window minus baseline-window lens mean shifts.",
        "encoding": "X-axis is annotation-point shift; y-axis lists lenses.",
        "interpretive_note": "Use as a compact temporal comparison.",
    },
    "27_distribution_share_shifts": {
        "method": "Recent-vs-baseline share-change chart for sources and tags.",
        "encoding": "X-axis is percentage-point share change; y-axis lists groups.",
        "interpretive_note": "Use as distribution movement context.",
    },
    "28_focus_lens_source_means": {
        "method": "Source mean chart for the strongest pooled source-effect lens.",
        "encoding": "Bars show mean annotation value by source for one selected lens.",
        "interpretive_note": "Pooled source means are descriptive and topic-confounded.",
    },
    "29_lens_plurality_panel": {
        "method": "Article-level multi-lens plurality panel.",
        "encoding": "Center node is one article; surrounding nodes show selected lens values and interpretive prompts.",
        "interpretive_note": "This is the main example of one discourse object opened through multiple readings.",
    },
    "30_topic_lens_divergence": {
        "method": "Topic/tag divergence heatmap against corpus lens averages.",
        "encoding": "Rows are topic or tag slices; columns are selected lenses; color shows slice-minus-corpus annotation delta.",
        "interpretive_note": "Positive and negative cells mean stronger or weaker rubric agreement, not better or worse discourse.",
    },
    "31_event_plurality_panel": {
        "method": "Multi-source event-cluster schematic.",
        "encoding": "Center node is a shared event; surrounding nodes show sources, tags, coverage window, and inspectable trace.",
        "interpretive_note": "Use to show event-controlled comparative reading.",
    },
    "32_reduced_daily_lens_scores": {
        "method": "Reduced daily lens-score time series for a small lens set.",
        "encoding": "X-axis is date; y-axis is mean annotation value.",
        "interpretive_note": "Use only when temporal trajectories remain readable.",
    },
    "33_two_tag_lens_comparison": {
        "method": "Grouped bar comparison of two tag-defined discourse slices.",
        "encoding": "X-axis lists lenses; y-axis shows mean annotation value; color separates tags.",
        "interpretive_note": "Useful for precise comparison, but less visually distinctive than the radial fingerprint.",
    },
    "34_discourse_constellation": {
        "method": "Poster-readable tag constellation derived from tag lens-profile positions.",
        "encoding": "Each point is a tag; labels name nearby discourse formations; marker size reflects article count.",
        "interpretive_note": "Use as a map of discursive formations, avoiding visible ML terminology in poster copy.",
    },
    "35_two_tag_lens_fingerprints": {
        "method": "Radial comparison of two tag-defined lens profiles.",
        "encoding": "Each axis is a lens; polygon shape shows mean annotation profile for each tag.",
        "interpretive_note": "Use to foreground interpretive shape rather than exact measurement.",
    },
    "36_lens_drift_dumbbell": {
        "method": "Baseline-to-recent dumbbell chart for lens means.",
        "encoding": "Y-axis lists lenses; endpoints show baseline and recent mean annotation values; connector shows movement.",
        "interpretive_note": "Use as the clearest temporal movement figure.",
    },
    "37_tag_focus_temporal_lens_scores": {
        "method": "Single-tag temporal lens trajectory.",
        "encoding": "X-axis is week or date; y-axis is mean annotation value within one tag slice.",
        "interpretive_note": "Use when temporal movement should remain tied to one discourse object.",
    },
}


def figure_method_notes(spec: FigureSpec) -> dict[str, str]:
    notes = FIGURE_METHOD_NOTES.get(spec.id, {})
    return {
        "method": notes.get("method") or f"Poster figure generated by `{spec.builder}`.",
        "encoding": notes.get("encoding") or "Axes and color encodings are defined by the figure labels.",
        "interpretive_note": notes.get("interpretive_note") or "Interpret as computational annotation for comparative reading, not a final judgment.",
    }


def _lens_label(value: Any) -> str:
    text = str(value or "Unknown")
    return LENS_LABELS.get(text, _short_label(text, 22))


def _cluster_label_rows(rows: list[dict[str, Any]], *, limit: int = 14) -> list[dict[str, Any]]:
    cleaned: list[dict[str, Any]] = []
    for row in rows:
        tag = str(row.get("tag") or "").strip()
        if not tag:
            continue
        cleaned.append(
            {
                "tag": tag,
                "n_articles": int(_num(row.get("n_articles"), 0) or 0),
            }
        )
    cleaned.sort(key=lambda row: (-row["n_articles"], row["tag"].casefold()))
    return cleaned[:limit]


def tag_cluster_fingerprint(rows: list[dict[str, Any]]) -> str:
    payload = sorted(
        _cluster_label_rows(rows, limit=1000),
        key=lambda row: (row["tag"].casefold(), row["n_articles"]),
    )
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()[:16]


def set_tag_cluster_label_overrides(overrides: dict[str, str] | None) -> None:
    TAG_CLUSTER_LABEL_OVERRIDES.clear()
    if not overrides:
        return
    for fingerprint, label in overrides.items():
        clean = sanitize_tag_cluster_label(label)
        if fingerprint and clean:
            TAG_CLUSTER_LABEL_OVERRIDES[str(fingerprint)] = clean


def sanitize_tag_cluster_label(value: Any) -> str:
    text = " ".join(str(value or "").strip().split())
    text = text.replace("PCA", "").replace("KNN", "").replace("k-means", "").replace("embedding", "")
    text = " ".join(text.split())
    if not text:
        return ""
    return _short_label(text, 42)


def semantic_tag_cluster_label(rows: list[dict[str, Any]]) -> str:
    override = TAG_CLUSTER_LABEL_OVERRIDES.get(tag_cluster_fingerprint(rows))
    if override:
        return override
    weighted_scores: dict[str, float] = defaultdict(float)
    top_tags = sorted(rows, key=lambda row: (_num(row.get("n_articles"), 0) or 0), reverse=True)[:3]
    for row in rows:
        tag = str(row.get("tag") or "").lower()
        weight = _num(row.get("n_articles"), 1) or 1
        for label, keywords in TAG_SEMANTIC_LABELS:
            if any(keyword in tag for keyword in keywords):
                weighted_scores[label] += weight
    if weighted_scores:
        ranked = sorted(weighted_scores.items(), key=lambda item: (-item[1], item[0]))
        total_weight = sum(weighted_scores.values()) or 1
        strong_labels = [label for label, score in ranked[:2] if score / total_weight >= 0.25]
        if len(strong_labels) >= 2:
            return " / ".join(label.split(" / ")[0] for label in strong_labels)
        return ranked[0][0]
    return " / ".join(str(row.get("tag") or "Tag") for row in top_tags)


def _annotation_offset(centroid_x: float, centroid_y: float, center_x: float, center_y: float, index: int) -> tuple[int, int]:
    dx = centroid_x - center_x
    dy = centroid_y - center_y
    if abs(dx) < 0.15 and abs(dy) < 0.15:
        angle = (index / max(1, MAX_POSTER_TAG_CLUSTERS)) * 2 * math.pi
        return int(math.cos(angle) * 92), int(math.sin(angle) * -72)
    ax = 92 if dx >= 0 else -92
    ay = -72 if dy >= 0 else 72
    if index % 2:
        ax = int(ax * 0.72)
        ay = int(ay * 1.16)
    return ax, ay


def _weighted_tag_kmeans(rows: list[dict[str, Any]], max_clusters: int = MAX_POSTER_TAG_CLUSTERS) -> list[tuple[int, list[dict[str, Any]]]]:
    points = [
        (
            _num(row.get("pc1"), 0) or 0,
            _num(row.get("pc2"), 0) or 0,
            max(1.0, math.sqrt(_num(row.get("n_articles"), 1) or 1)),
        )
        for row in rows
    ]
    if not points:
        return []
    k = max(1, min(max_clusters, len(points), max(2, round(math.sqrt(len(points) / 2)))))

    first_index = max(range(len(points)), key=lambda index: points[index][2])
    centroid_indices = [first_index]
    while len(centroid_indices) < k:
        centroid_points = [points[index] for index in centroid_indices]

        def weighted_distance_score(index: int) -> float:
            x, y, weight = points[index]
            min_distance = min((x - cx) ** 2 + (y - cy) ** 2 for cx, cy, _ in centroid_points)
            return min_distance * weight

        next_index = max(range(len(points)), key=weighted_distance_score)
        if next_index in centroid_indices:
            break
        centroid_indices.append(next_index)

    centroids = [(points[index][0], points[index][1]) for index in centroid_indices]
    assignments = [0 for _ in points]
    for _ in range(40):
        next_assignments = []
        for x, y, _ in points:
            next_assignments.append(min(range(len(centroids)), key=lambda index: (x - centroids[index][0]) ** 2 + (y - centroids[index][1]) ** 2))
        if next_assignments == assignments:
            break
        assignments = next_assignments
        next_centroids: list[tuple[float, float]] = []
        for cluster_index in range(len(centroids)):
            members = [index for index, assignment in enumerate(assignments) if assignment == cluster_index]
            if not members:
                next_centroids.append(centroids[cluster_index])
                continue
            total_weight = sum(points[index][2] for index in members)
            next_centroids.append(
                (
                    sum(points[index][0] * points[index][2] for index in members) / total_weight,
                    sum(points[index][1] * points[index][2] for index in members) / total_weight,
                )
            )
        centroids = next_centroids

    grouped: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for row, assignment in zip(rows, assignments):
        grouped[assignment].append(row)
    ordered = sorted(grouped.values(), key=lambda cluster_rows: -sum(_num(row.get("n_articles"), 0) or 0 for row in cluster_rows))
    return [(index + 1, cluster_rows) for index, cluster_rows in enumerate(ordered)]


def _tag_lens_cluster_rows(derived: dict[str, Any]) -> list[dict[str, Any]]:
    rows = [_as_dict(row) for row in _as_list(_as_dict(derived.get("tag_lens_pca")).get("tag_points"))]
    return [
        row
        for row in rows
        if _num(row.get("pc1")) is not None and _num(row.get("pc2")) is not None and str(row.get("tag") or "").strip()
    ]


def tag_cluster_label_payload(derived: dict[str, Any]) -> dict[str, Any]:
    rows = _tag_lens_cluster_rows(derived)
    clusters = _weighted_tag_kmeans(rows) if rows else []
    return {
        "input_policy": "Only tag labels and article counts are supplied for labeling.",
        "clusters": [
            {
                "cluster_id": cluster_id,
                "fingerprint": tag_cluster_fingerprint(cluster_rows),
                "tags": _cluster_label_rows(cluster_rows),
            }
            for cluster_id, cluster_rows in clusters
        ],
    }


def _tag_cluster_label_messages(payload: dict[str, Any]) -> list[dict[str, str]]:
    return [
        {
            "role": "system",
            "content": (
                "You label groups of news tags for an interpretive media-studies poster. "
                "Use only the tag labels and article counts in the user message. "
                "Do not use outside facts, conversation context, model memory, PCA coordinates, embeddings, or source names. "
                "Return compact, non-normative interpretive labels."
            ),
        },
        {
            "role": "user",
            "content": (
                "Name each cluster with a 2-5 word title-case noun phrase. "
                "Prefer phrases like institutional legitimacy, public health risk, economic pressure, security rhetoric, "
                "labor politics, humanitarian discourse, climate crisis, or technology governance when supported by tags. "
                "Avoid ML terms, rankings, truth claims, and value judgments. "
                "Return JSON only with this shape: "
                '{"labels":[{"fingerprint":"...","label":"...","rationale":"short phrase grounded in tags"}]}\n\n'
                f"{json.dumps(payload, ensure_ascii=False, indent=2)}"
            ),
        },
    ]


def parse_tag_cluster_label_response(content: str, payload: dict[str, Any]) -> dict[str, str]:
    try:
        parsed = json.loads(content)
    except json.JSONDecodeError as exc:
        raise ValueError("OpenAI tag-cluster label response was not valid JSON.") from exc
    known = {str(row.get("fingerprint")) for row in _as_list(payload.get("clusters"))}
    labels: dict[str, str] = {}
    for row in _as_list(_as_dict(parsed).get("labels")):
        item = _as_dict(row)
        fingerprint = str(item.get("fingerprint") or "")
        label = sanitize_tag_cluster_label(item.get("label"))
        if fingerprint in known and label:
            labels[fingerprint] = label
    missing = sorted(known - set(labels))
    if missing:
        raise ValueError(f"OpenAI tag-cluster label response omitted {len(missing)} cluster label(s).")
    return labels


def request_openai_tag_cluster_labels(
    payload: dict[str, Any],
    *,
    model: str = DEFAULT_TAG_CLUSTER_LABEL_MODEL,
    api_key: str | None = None,
) -> dict[str, str]:
    key = api_key or os.environ.get("OPENAI_API_KEY")
    if not key:
        raise RuntimeError("OPENAI_API_KEY is required to generate GPT tag-cluster labels.")
    try:
        from openai import OpenAI
    except Exception as exc:  # pragma: no cover - dependency is installed in normal environments.
        raise RuntimeError("openai package is not installed.") from exc
    client = OpenAI(api_key=key)
    response = client.chat.completions.create(
        model=model,
        temperature=0,
        response_format={"type": "json_object"},
        messages=_tag_cluster_label_messages(payload),
    )
    content = response.choices[0].message.content or ""
    return parse_tag_cluster_label_response(content, payload)


def write_openai_tag_cluster_label_file(
    *,
    derived: dict[str, Any],
    output_path: Path,
    model: str = DEFAULT_TAG_CLUSTER_LABEL_MODEL,
) -> dict[str, Any]:
    payload = tag_cluster_label_payload(derived)
    labels = request_openai_tag_cluster_labels(payload, model=model)
    output = {
        "generated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "model": model,
        "input_policy": payload["input_policy"],
        "labels": [
            {
                "fingerprint": cluster["fingerprint"],
                "label": labels.get(cluster["fingerprint"], ""),
                "tags": cluster["tags"],
            }
            for cluster in payload["clusters"]
        ],
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(output, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return output


def load_tag_cluster_label_overrides(path: Path | None) -> dict[str, str]:
    if not path:
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    rows = _as_list(_as_dict(data).get("labels"))
    return {
        str(_as_dict(row).get("fingerprint")): sanitize_tag_cluster_label(_as_dict(row).get("label"))
        for row in rows
        if _as_dict(row).get("fingerprint") and sanitize_tag_cluster_label(_as_dict(row).get("label"))
    }


def _top_mapping_rows(value: Any, *, label_key: str, limit: int = 15) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if isinstance(value, dict):
        rows = [{label_key: key, "count": _num(count, 0) or 0} for key, count in value.items()]
    elif isinstance(value, list):
        for item in value:
            row = _as_dict(item)
            label = row.get(label_key)
            if label is None:
                continue
            rows.append({label_key: str(label), "count": _num(row.get("count"), 0) or 0})
    rows.sort(key=lambda row: (-row["count"], str(row[label_key])))
    return rows[:limit]


def _normalized_source(value: Any) -> str:
    return " ".join(str(value or "").strip().lower().split())


def parse_source_filter(value: str | None) -> tuple[str, ...]:
    if not value:
        return ()
    return tuple(source.strip() for source in value.split(",") if source.strip())


def _required_available(derived: dict[str, Any], spec: FigureSpec) -> tuple[bool, str]:
    missing = [key for key in spec.required_keys if not derived.get(key)]
    if missing:
        return False, f"Missing required derived keys: {', '.join(missing)}"
    for key in spec.required_keys:
        value = derived.get(key)
        if isinstance(value, dict) and str(value.get("status") or "ok") == "unavailable":
            return False, str(value.get("reason") or f"{key} unavailable")
    return True, ""


def _typography_scale(width: int, height: int) -> float:
    width_scale = width / DEFAULT_WIDTH
    height_scale = height / DEFAULT_HEIGHT
    return min(max((width_scale + height_scale) / 2.0, 0.85), 1.35)


def _scaled_font_size(spec: FigureSpec, base: int, *, minimum: int | None = None, maximum: int | None = None) -> int:
    size = int(round(base * _typography_scale(spec.width, spec.height)))
    if minimum is not None:
        size = max(size, minimum)
    if maximum is not None:
        size = min(size, maximum)
    return size


def _font_size(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _font_size_at_least(value: Any, minimum: int) -> int:
    existing = _font_size(value)
    if existing is None:
        return minimum
    return int(round(max(existing, minimum)))


def _base_layout(
    title: str,
    *,
    width: int = DEFAULT_WIDTH,
    height: int = DEFAULT_HEIGHT,
    show_title: bool = True,
) -> dict[str, Any]:
    scale = _typography_scale(width, height)
    body_size = int(round(18 * scale))
    title_size = int(round(28 * scale))
    return {
        "title": {
            "text": title if show_title else "",
            "x": 0.02,
            "xanchor": "left",
            "font": {"size": title_size},
        },
        "template": "plotly_white",
        "width": width,
        "height": height,
        "font": {"family": "Arial, Helvetica, sans-serif", "size": body_size, "color": "#172033"},
        "paper_bgcolor": "white",
        "plot_bgcolor": "white",
        "margin": {"l": 95, "r": 45, "t": 105, "b": 90},
        "legend": {"orientation": "h", "y": -0.18, "x": 0, "font": {"size": int(round(16 * scale))}},
    }


def _apply_scaled_typography(figure: go.Figure, spec: FigureSpec) -> go.Figure:
    layout_size = _scaled_font_size(spec, 18, minimum=15)
    title_size = _scaled_font_size(spec, 28, minimum=22)
    tick_size = _scaled_font_size(spec, 15, minimum=13)
    axis_title_size = _scaled_font_size(spec, 17, minimum=15)
    legend_size = _scaled_font_size(spec, 16, minimum=14)
    annotation_min_size = _scaled_font_size(spec, 16, minimum=14)
    trace_text_min_size = _scaled_font_size(spec, 14, minimum=13)
    colorbar_tick_size = _scaled_font_size(spec, 13, minimum=12)
    colorbar_title_size = _scaled_font_size(spec, 14, minimum=13)

    figure.update_layout(
        font={"family": "Arial, Helvetica, sans-serif", "size": layout_size, "color": "#172033"},
        title={"font": {"size": title_size}},
        legend={"font": {"size": legend_size}},
    )
    figure.update_xaxes(tickfont={"size": tick_size}, title_font={"size": axis_title_size})
    figure.update_yaxes(tickfont={"size": tick_size}, title_font={"size": axis_title_size})

    annotations = list(figure.layout.annotations or [])
    for annotation in annotations:
        font = annotation.font
        font_size = _font_size_at_least(getattr(font, "size", None), annotation_min_size)
        if font:
            font.size = font_size
        else:
            annotation.font = {"size": font_size}

    layout_json = figure.layout.to_plotly_json()
    polar = layout_json.get("polar") if isinstance(layout_json.get("polar"), dict) else {}
    if polar:
        polar_update: dict[str, Any] = {}
        radialaxis = polar.get("radialaxis") if isinstance(polar.get("radialaxis"), dict) else {}
        angularaxis = polar.get("angularaxis") if isinstance(polar.get("angularaxis"), dict) else {}
        radial_tick = _font_size_at_least(_as_dict(radialaxis.get("tickfont")).get("size"), tick_size)
        angular_tick = _font_size_at_least(_as_dict(angularaxis.get("tickfont")).get("size"), tick_size)
        polar_update["radialaxis"] = {"tickfont": {"size": radial_tick}}
        polar_update["angularaxis"] = {"tickfont": {"size": angular_tick}}
        figure.update_layout(polar=polar_update)

    for trace in figure.data:
        trace_json = trace.to_plotly_json()
        textfont = trace_json.get("textfont") if isinstance(trace_json.get("textfont"), dict) else {}
        if trace_json.get("text") is not None or trace_json.get("texttemplate") is not None or textfont:
            trace.update(textfont={"size": _font_size_at_least(textfont.get("size"), trace_text_min_size)})

        colorbar = trace_json.get("colorbar") if isinstance(trace_json.get("colorbar"), dict) else {}
        if colorbar:
            title = colorbar.get("title")
            title_obj = title if isinstance(title, dict) else {}
            title_font = title_obj.get("font") if isinstance(title_obj.get("font"), dict) else {}
            trace.update(
                colorbar={
                    "tickfont": {"size": _font_size_at_least(_as_dict(colorbar.get("tickfont")).get("size"), colorbar_tick_size)},
                    "title": {
                        "font": {"size": _font_size_at_least(title_font.get("size"), colorbar_title_size)}
                    },
                }
            )

        marker = trace_json.get("marker") if isinstance(trace_json.get("marker"), dict) else {}
        marker_colorbar = marker.get("colorbar") if isinstance(marker.get("colorbar"), dict) else {}
        if marker_colorbar:
            title = marker_colorbar.get("title")
            title_obj = title if isinstance(title, dict) else {}
            title_font = title_obj.get("font") if isinstance(title_obj.get("font"), dict) else {}
            trace.update(
                marker={
                    "colorbar": {
                        "tickfont": {
                            "size": _font_size_at_least(
                                _as_dict(marker_colorbar.get("tickfont")).get("size"),
                                colorbar_tick_size,
                            )
                        },
                        "title": {
                            "font": {
                                "size": _font_size_at_least(title_font.get("size"), colorbar_title_size)
                            }
                        },
                    }
                }
            )

    return figure


def _finalize_figure(figure: go.Figure, spec: FigureSpec) -> go.Figure:
    figure.update_layout(**_base_layout(spec.title, width=spec.width, height=spec.height, show_title=spec.show_title))
    figure.update_xaxes(showgrid=True, gridcolor="#e5e7eb", zerolinecolor="#9ca3af")
    figure.update_yaxes(showgrid=True, gridcolor="#e5e7eb", zerolinecolor="#9ca3af")
    return _apply_scaled_typography(figure, spec)


def _placeholder(spec: FigureSpec, reason: str) -> BuiltFigure:
    figure = go.Figure()
    figure.add_annotation(
        text=f"{spec.title}<br><br>Unavailable<br>{reason}",
        x=0.5,
        y=0.5,
        xref="paper",
        yref="paper",
        showarrow=False,
        align="center",
        font={"size": 28, "color": "#374151"},
    )
    figure.update_xaxes(visible=False)
    figure.update_yaxes(visible=False)
    _finalize_figure(figure, spec)
    return BuiltFigure(figure=figure, caption=f"{spec.caption} Unavailable: {reason}", status="unavailable", reason=reason)


def _resolve_source_order(rows: list[Any], requested_sources: tuple[str, ...]) -> list[str]:
    available: dict[str, str] = {}
    for row in rows:
        row_obj = _as_dict(row)
        for source in {
            *_as_dict(row_obj.get("source_counts")).keys(),
            *_as_dict(row_obj.get("source_means")).keys(),
        }:
            available.setdefault(_normalized_source(source), str(source))
    return [available[_normalized_source(source)] for source in requested_sources if _normalized_source(source) in available]


def filter_derived_for_sources(derived: dict[str, Any], requested_sources: tuple[str, ...]) -> dict[str, Any]:
    if not requested_sources:
        return derived
    filtered = dict(derived)
    effects = _as_dict(derived.get("source_lens_effects"))
    rows = _as_list(effects.get("rows"))
    source_order = _resolve_source_order(rows, requested_sources)
    if not effects or not source_order:
        return filtered
    filtered_rows = []
    for row in rows:
        row_obj = dict(_as_dict(row))
        source_means = _as_dict(row_obj.get("source_means"))
        source_counts = _as_dict(row_obj.get("source_counts"))
        row_obj["source_means"] = {source: source_means[source] for source in source_order if source in source_means}
        row_obj["source_counts"] = {source: source_counts[source] for source in source_order if source in source_counts}
        filtered_rows.append(row_obj)
    filtered_effects = dict(effects)
    filtered_effects["rows"] = filtered_rows
    filtered_effects["_source_filter_order"] = source_order
    filtered["source_lens_effects"] = filtered_effects
    return filtered


def _matrix_from_source_effects(source_lens_effects: dict[str, Any]) -> tuple[list[str], list[str], list[list[float | None]], dict[str, int]]:
    rows = _as_list(source_lens_effects.get("rows"))
    requested_order = [str(source) for source in _as_list(source_lens_effects.get("_source_filter_order")) if str(source)]
    source_totals: dict[str, float] = defaultdict(float)
    source_counts: dict[str, int] = {}
    for row in rows:
        for source, count in _as_dict(_as_dict(row).get("source_counts")).items():
            count_value = _num(count, 0.0) or 0.0
            source_totals[source] += count_value
            source_counts[source] = max(source_counts.get(source, 0), int(count_value))
    if requested_order:
        sources = [source for source in requested_order if source in source_totals or any(source in _as_dict(_as_dict(row).get("source_means")) for row in rows)]
    else:
        sources = sorted(source_totals, key=lambda source: (-source_totals[source], source))
    if not sources:
        source_names = set()
        for row in rows:
            source_names.update(_as_dict(_as_dict(row).get("source_means")).keys())
        sources = sorted(source_names)
    lenses = [str(_as_dict(row).get("lens") or "Unknown") for row in rows]
    z = []
    for row in rows:
        means = _as_dict(_as_dict(row).get("source_means"))
        z.append([_num(means.get(source)) for source in sources])
    return sources, lenses, z, source_counts


def build_source_lens_matrix(derived: dict[str, Any], spec: FigureSpec) -> BuiltFigure:
    sources, lenses, z, source_counts = _matrix_from_source_effects(_as_dict(derived.get("source_lens_effects")))
    if not sources or not lenses:
        return _placeholder(spec, "No source/lens means available.")
    x_labels = [
        f"{_short_label(source, 22)}<br>n={source_counts[source]}" if source in source_counts else _short_label(source, 22)
        for source in sources
    ]
    y_labels = [_lens_label(lens) for lens in lenses]
    cell_text = [["" if value is None else f"{value:.0f}" for value in row] for row in z]
    figure = go.Figure(
        data=[
            go.Heatmap(
                z=z,
                x=x_labels,
                y=y_labels,
                text=cell_text,
                texttemplate="%{text}",
                textfont={"size": 16, "color": "white"},
                colorscale=LENS_SCORE_HEATMAP_COLORSCALE,
                zmin=0,
                zmax=100,
                colorbar={"title": "Mean<br>annotation<br>value", "ticksuffix": ""},
                hovertemplate="Source: %{x}<br>Lens: %{y}<br>Mean annotation: %{z:.1f}<extra></extra>",
            )
        ]
    )
    figure.update_layout(
        xaxis={"tickangle": 0, "side": "top"},
        yaxis={"autorange": "reversed"},
        margin={"l": 210, "r": 75, "t": 125, "b": 55},
    )
    return BuiltFigure(_finalize_figure(figure, spec), spec.caption)


def build_lens_correlation_heatmap(derived: dict[str, Any], spec: FigureSpec) -> BuiltFigure:
    correlations = _as_dict(derived.get("lens_correlations"))
    lenses = _as_list(correlations.get("lenses"))
    matrix = _as_dict(correlations.get("correlation")).get("raw")
    if not lenses or not matrix:
        return _placeholder(spec, "No raw correlation matrix available.")
    labels = [_lens_label(lens) for lens in lenses]
    cell_text = [[f"{_num(value, 0) or 0:.2f}" for value in row] for row in matrix]
    figure = go.Figure(
        data=[
            go.Heatmap(
                z=matrix,
                x=labels,
                y=labels,
                text=cell_text,
                texttemplate="%{text}",
                textfont={"size": 11, "color": "#111827"},
                colorscale="RdBu",
                zmin=-1,
                zmax=1,
                colorbar={"title": "Correlation<br>r"},
                hovertemplate="Lens A: %{x}<br>Lens B: %{y}<br>r: %{z:.2f}<extra></extra>",
            )
        ]
    )
    figure.update_layout(xaxis={"tickangle": -35}, yaxis={"autorange": "reversed"}, margin={"l": 210, "r": 70, "t": 105, "b": 180})
    return BuiltFigure(_finalize_figure(figure, spec), spec.caption)


def build_lens_pca_variance(derived: dict[str, Any], spec: FigureSpec) -> BuiltFigure:
    rows = _as_list(_as_dict(derived.get("lens_pca")).get("explained_variance"))
    rows = [row for row in map(_as_dict, rows) if row.get("component")]
    if not rows:
        return _placeholder(spec, "No latent variance rows available.")
    x = [str(row.get("component")) for row in rows]
    explained = [(_num(row.get("explained_variance_ratio"), 0) or 0) * 100 for row in rows]
    cumulative = [(_num(row.get("cumulative_variance_ratio"), 0) or 0) * 100 for row in rows]
    figure = go.Figure()
    figure.add_bar(
        x=x,
        y=explained,
        name="Single component",
        marker={"color": PALETTE[0]},
        text=[f"{value:.1f}%" for value in explained],
        textposition="outside",
    )
    figure.add_scatter(
        x=x,
        y=cumulative,
        name="Cumulative",
        mode="lines+markers+text",
        text=[f"{value:.0f}%" for value in cumulative],
        textposition="top center",
        line={"color": PALETTE[1], "width": 4},
    )
    figure.update_layout(yaxis={"title": "Variance explained (%)", "range": [0, 105]})
    return BuiltFigure(_finalize_figure(figure, spec), spec.caption)


def _group_points_by_source(points: list[dict[str, Any]], x_key: str, y_key: str) -> list[tuple[str, list[dict[str, Any]]]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in points:
        x = _num(row.get(x_key))
        y = _num(row.get(y_key))
        if x is None or y is None:
            continue
        grouped[str(row.get("source") or "Unknown")].append(row)
    return sorted(grouped.items(), key=lambda item: (-len(item[1]), item[0]))


def _source_space_figure(payload: dict[str, Any], spec: FigureSpec, x_key: str, y_key: str, centroid_x: str, centroid_y: str) -> BuiltFigure:
    points = [_as_dict(row) for row in _as_list(payload.get("article_points"))]
    centroids = [_as_dict(row) for row in _as_list(payload.get("source_centroids"))]
    grouped = _group_points_by_source(points, x_key, y_key)
    if not grouped:
        return _placeholder(spec, f"No {x_key}/{y_key} article points available.")
    figure = go.Figure()
    for index, (source, rows) in enumerate(grouped):
        figure.add_scatter(
            x=[_num(row.get(x_key)) for row in rows],
            y=[_num(row.get(y_key)) for row in rows],
            name=source,
            mode="markers",
            text=[str(row.get("title") or "Untitled") for row in rows],
            marker={"size": 7, "opacity": 0.48, "color": PALETTE[index % len(PALETTE)]},
            hovertemplate="%{text}<br>%{fullData.name}<br>x: %{x:.2f}<br>y: %{y:.2f}<extra></extra>",
        )
    centroid_rows = [row for row in centroids if _num(row.get(centroid_x)) is not None and _num(row.get(centroid_y)) is not None]
    if centroid_rows:
        figure.add_scatter(
            x=[_num(row.get(centroid_x)) for row in centroid_rows],
            y=[_num(row.get(centroid_y)) for row in centroid_rows],
            name="Source centroids",
            mode="markers+text",
            text=[str(row.get("source") or "Unknown") for row in centroid_rows],
            textposition="top center",
            marker={"symbol": "x", "size": 16, "color": "#111827", "line": {"width": 2}},
            hovertemplate="%{text}<br>x: %{x:.2f}<br>y: %{y:.2f}<extra></extra>",
        )
    axis_prefix = "Lens contrast" if x_key.startswith("pc") else "Distance axis"
    figure.update_layout(xaxis={"title": f"{axis_prefix} 1"}, yaxis={"title": f"{axis_prefix} 2"})
    return BuiltFigure(_finalize_figure(figure, spec), spec.caption)


def build_article_pca_source_space(derived: dict[str, Any], spec: FigureSpec) -> BuiltFigure:
    return _source_space_figure(_as_dict(derived.get("lens_pca")), spec, "pc1", "pc2", "pc1", "pc2")


def build_article_mds_source_space(derived: dict[str, Any], spec: FigureSpec) -> BuiltFigure:
    return _source_space_figure(_as_dict(derived.get("lens_mds")), spec, "mds1", "mds2", "mds1", "mds2")


def build_tag_lens_pca_clusters(derived: dict[str, Any], spec: FigureSpec) -> BuiltFigure:
    rows = [_as_dict(row) for row in _as_list(_as_dict(derived.get("tag_lens_pca")).get("tag_points"))]
    rows = [row for row in rows if _num(row.get("pc1")) is not None and _num(row.get("pc2")) is not None]
    if not rows:
        return _placeholder(spec, "No tag lens-space points available.")
    globally_labeled = {
        str(row.get("tag") or "")
        for row in sorted(rows, key=lambda row: (_num(row.get("n_articles"), 0) or 0), reverse=True)[:14]
    }
    figure = go.Figure()
    clusters = _weighted_tag_kmeans(rows)
    center_x = sum((_num(row.get("pc1"), 0) or 0) for row in rows) / len(rows)
    center_y = sum((_num(row.get("pc2"), 0) or 0) for row in rows) / len(rows)
    annotations: list[dict[str, Any]] = []
    for index, (cluster, cluster_rows) in enumerate(clusters):
        cluster_article_count = sum(_num(row.get("n_articles"), 0) or 0 for row in cluster_rows)
        cluster_label = semantic_tag_cluster_label(cluster_rows)
        cluster_top_tag_rows = sorted(cluster_rows, key=lambda row: (_num(row.get("n_articles"), 0) or 0), reverse=True)[:3]
        cluster_top_tags = {
            str(row.get("tag") or "")
            for row in cluster_top_tag_rows
        }
        top_tag_summary = ", ".join(_short_label(row.get("tag"), 18) for row in cluster_top_tag_rows)
        figure.add_scatter(
            x=[_num(row.get("pc1")) for row in cluster_rows],
            y=[_num(row.get("pc2")) for row in cluster_rows],
            name=f"{cluster_label} ({len(cluster_rows)} tags)",
            mode="markers+text",
            text=[
                str(row.get("tag") or "")
                if str(row.get("tag") or "") in globally_labeled or str(row.get("tag") or "") in cluster_top_tags
                else ""
                for row in cluster_rows
            ],
            textposition="top center",
            customdata=[_num(row.get("n_articles"), 0) or 0 for row in cluster_rows],
            marker={
                "size": [max(8, min(32, math.sqrt(_num(row.get("n_articles"), 1) or 1) * 4)) for row in cluster_rows],
                "color": PALETTE[index % len(PALETTE)],
                "opacity": 0.76,
                "line": {"color": "white", "width": 1},
            },
            hovertemplate="%{text}<br>Articles: %{customdata}<br>Lens axis 1: %{x:.2f}<br>Lens axis 2: %{y:.2f}<extra></extra>",
        )
        centroid_x = sum((_num(row.get("pc1"), 0) or 0) for row in cluster_rows) / len(cluster_rows)
        centroid_y = sum((_num(row.get("pc2"), 0) or 0) for row in cluster_rows) / len(cluster_rows)
        ax, ay = _annotation_offset(centroid_x, centroid_y, center_x, center_y, index)
        annotations.append(
            {
                "x": centroid_x,
                "y": centroid_y,
                "text": f"{cluster_label}<br>{top_tag_summary}<br>{len(cluster_rows)} tags / {int(cluster_article_count)} articles",
                "showarrow": True,
                "arrowhead": 2,
                "arrowsize": 1,
                "arrowwidth": 1,
                "arrowcolor": "#475569",
                "ax": ax,
                "ay": ay,
                "font": {"size": 13, "color": "#111827"},
                "bgcolor": "rgba(255,255,255,0.9)",
                "bordercolor": "#cbd5e1",
                "borderwidth": 1,
                "borderpad": 4,
            }
        )
    figure.update_layout(
        xaxis={"title": "Lens contrast axis 1"},
        yaxis={"title": "Lens contrast axis 2"},
        annotations=annotations,
        legend={"title": {"text": "Semantic tag clusters"}},
    )
    return BuiltFigure(_finalize_figure(figure, spec), spec.caption)


def build_discourse_constellation(derived: dict[str, Any], spec: FigureSpec) -> BuiltFigure:
    rows = [_as_dict(row) for row in _as_list(_as_dict(derived.get("tag_lens_pca")).get("tag_points"))]
    rows = [row for row in rows if _num(row.get("pc1")) is not None and _num(row.get("pc2")) is not None]
    if not rows:
        return _placeholder(spec, "No tag lens-space points available.")

    clusters = _weighted_tag_kmeans(rows)
    figure = go.Figure()
    for index, (_cluster, cluster_rows) in enumerate(clusters):
        cluster_label = semantic_tag_cluster_label(cluster_rows)
        cluster_rows = sorted(cluster_rows, key=lambda row: (_num(row.get("n_articles"), 0) or 0), reverse=True)
        centroid_x = sum((_num(row.get("pc1"), 0) or 0) for row in cluster_rows) / len(cluster_rows)
        centroid_y = sum((_num(row.get("pc2"), 0) or 0) for row in cluster_rows) / len(cluster_rows)
        top_rows = cluster_rows[:3]
        for row in top_rows:
            figure.add_shape(
                type="line",
                x0=centroid_x,
                y0=centroid_y,
                x1=_num(row.get("pc1"), 0) or 0,
                y1=_num(row.get("pc2"), 0) or 0,
                line={"color": "rgba(100, 116, 139, 0.26)", "width": 2},
                layer="below",
            )
        figure.add_scatter(
            x=[_num(row.get("pc1")) for row in cluster_rows],
            y=[_num(row.get("pc2")) for row in cluster_rows],
            mode="markers+text",
            name=cluster_label,
            text=[_short_label(row.get("tag"), 18) if row in top_rows else "" for row in cluster_rows],
            textposition="top center",
            customdata=[_num(row.get("n_articles"), 0) or 0 for row in cluster_rows],
            marker={
                "size": [max(8, min(30, math.sqrt(_num(row.get("n_articles"), 1) or 1) * 4.2)) for row in cluster_rows],
                "color": PALETTE[index % len(PALETTE)],
                "opacity": 0.72,
                "line": {"color": "white", "width": 1.5},
            },
            hovertemplate="%{text}<br>Articles: %{customdata}<extra></extra>",
        )
        figure.add_shape(
            type="circle",
            xref="x",
            yref="y",
            x0=centroid_x - 0.16,
            x1=centroid_x + 0.16,
            y0=centroid_y - 0.16,
            y1=centroid_y + 0.16,
            fillcolor="rgba(17, 24, 39, 0.12)",
            line={"color": "rgba(17, 24, 39, 0.72)", "width": 2},
            layer="below",
        )
        figure.add_annotation(
            x=centroid_x,
            y=centroid_y,
            text=cluster_label,
            showarrow=False,
            xanchor="left",
            xshift=14,
            align="left",
            font={"size": 16, "color": "#111827"},
            bgcolor="rgba(255,255,255,0.84)",
            bordercolor="rgba(148, 163, 184, 0.65)",
            borderwidth=1,
            borderpad=4,
        )

    finalized = _finalize_figure(figure, spec)
    finalized.update_layout(
        plot_bgcolor="#fffaf0",
        xaxis={"title": "PC1", "showticklabels": False, "zeroline": False},
        yaxis={"title": "PC2", "showticklabels": False, "zeroline": False},
        showlegend=False,
        margin={"l": 80, "r": 150, "t": 70, "b": 80},
    )
    return BuiltFigure(finalized, spec.caption)


def build_group_latent_source_centroids(derived: dict[str, Any], spec: FigureSpec) -> BuiltFigure:
    rows = [_as_dict(row) for row in _as_list(_as_dict(_as_dict(derived.get("group_latent_space")).get("groups")).get("source"))]
    rows = [row for row in rows if _num(row.get("pc1")) is not None and _num(row.get("pc2")) is not None]
    if not rows:
        return _placeholder(spec, "No source centroid rows available.")
    figure = go.Figure(
        data=[
            go.Scatter(
                x=[_num(row.get("pc1")) for row in rows],
                y=[_num(row.get("pc2")) for row in rows],
                text=[str(row.get("group") or "Unknown") for row in rows],
                customdata=[_num(row.get("n_articles"), 0) or 0 for row in rows],
                mode="markers+text",
                textposition="top center",
                marker={
                    "size": [max(12, min(38, math.sqrt(_num(row.get("n_articles"), 1) or 1) * 3.2)) for row in rows],
                    "color": PALETTE[1],
                    "opacity": 0.82,
                    "line": {"color": "#1e3a8a", "width": 1},
                },
                hovertemplate="%{text}<br>Articles: %{customdata}<br>Lens axis 1: %{x:.2f}<br>Lens axis 2: %{y:.2f}<extra></extra>",
            )
        ]
    )
    figure.update_layout(xaxis={"title": "Lens contrast axis 1"}, yaxis={"title": "Lens contrast axis 2"})
    return BuiltFigure(_finalize_figure(figure, spec), spec.caption)


def build_tag_momentum(derived: dict[str, Any], spec: FigureSpec) -> BuiltFigure:
    rows = [_as_dict(row) for row in _as_list(_as_dict(derived.get("tag_momentum")).get("rows"))]
    rows.sort(key=lambda row: (_num(row.get("momentum_score"), 0) or 0), reverse=True)
    max_rows = 8 if not spec.show_title else 15
    rows = rows[:max_rows]
    if not rows:
        return _placeholder(spec, "No tag momentum rows available.")
    scores = [_num(row.get("momentum_score"), 0) or 0 for row in rows]
    max_score = max(scores) if scores else 1
    figure = go.Figure(
        data=[
            go.Bar(
                x=[_num(row.get("momentum_score"), 0) or 0 for row in rows[::-1]],
                y=[_short_label(row.get("tag"), 26) for row in rows[::-1]],
                orientation="h",
                marker={"color": PALETTE[0]},
                text=[f"{(_num(row.get('momentum_score'), 0) or 0):.1f}" for row in rows[::-1]],
                textposition="outside",
                textfont={"size": 24, "color": "#172033"},
                cliponaxis=False,
                customdata=[[row.get("trend"), row.get("recent_count"), row.get("baseline_count")] for row in rows[::-1]],
                hovertemplate="Tag: %{y}<br>Momentum index: %{x:.2f}<br>Trend: %{customdata[0]}<br>Recent count: %{customdata[1]}<br>Baseline count: %{customdata[2]}<extra></extra>",
            )
        ]
    )
    figure.add_annotation(
        xref="paper",
        yref="paper",
        x=0,
        y=1.03,
        text="Top tags by recent attention movement.",
        showarrow=False,
        align="left",
        font={"size": 24, "color": "#475569"},
    )
    figure.update_layout(
        xaxis={"title": "Momentum index", "range": [0, max_score * 1.12]},
        yaxis={"title": ""},
        bargap=0.24,
        margin={"l": 190, "r": 90, "t": 70, "b": 75},
    )
    finalized = _finalize_figure(figure, spec)
    finalized.update_layout(margin={"l": 190, "r": 90, "t": 70, "b": 75}, bargap=0.24)
    finalized.update_xaxes(title_text="Momentum index", range=[0, max_score * 1.12], tickfont={"size": 23}, title_font={"size": 25})
    finalized.update_yaxes(title_text="", tickfont={"size": 26})
    finalized.update_traces(textfont={"size": 24, "color": "#172033"}, selector={"type": "bar"})
    return BuiltFigure(finalized, spec.caption)


def build_temporal_centroid_path(derived: dict[str, Any], spec: FigureSpec) -> BuiltFigure:
    rows = [_as_dict(row) for row in _as_list(_as_dict(derived.get("lens_temporal_embedding")).get("day_centroids"))]
    rows = [row for row in rows if row.get("date") and _num(row.get("pc1")) is not None and _num(row.get("pc2")) is not None]
    rows.sort(key=lambda row: str(row.get("date")))
    if not rows:
        return _placeholder(spec, "No daily lens-space centroid rows available.")
    label_dates = {0, len(rows) - 1}
    if len(rows) > 10:
        label_dates.update(range(0, len(rows), max(1, len(rows) // 5)))
    text_labels = [str(row.get("date")) if index in label_dates else "" for index, row in enumerate(rows)]
    figure = go.Figure(
        data=[
            go.Scatter(
                x=[_num(row.get("pc1")) for row in rows],
                y=[_num(row.get("pc2")) for row in rows],
                text=text_labels,
                customdata=[str(row.get("date")) for row in rows],
                mode="lines+markers+text",
                textposition="top center",
                marker={
                    "size": [max(8, min(26, math.sqrt(_num(row.get("count"), 1) or 1) * 2.4)) for row in rows],
                    "color": PALETTE[0],
                },
                line={"color": PALETTE[0], "width": 3},
                hovertemplate="Date: %{customdata}<br>Lens axis 1: %{x:.2f}<br>Lens axis 2: %{y:.2f}<extra></extra>",
            )
        ]
    )
    figure.update_layout(xaxis={"title": "Lens contrast axis 1"}, yaxis={"title": "Lens contrast axis 2"})
    return BuiltFigure(_finalize_figure(figure, spec), spec.caption)


def build_source_differentiation(derived: dict[str, Any], spec: FigureSpec) -> BuiltFigure:
    diff = _as_dict(derived.get("source_differentiation"))
    classification = _as_dict(diff.get("classification"))
    accuracy = _num(classification.get("accuracy"))
    baseline = _num(classification.get("baseline_accuracy"))
    if accuracy is None or baseline is None:
        return _placeholder(spec, "No pooled source classification metrics available.")
    figure = go.Figure(
        data=[
            go.Bar(
                x=["Observed separation", "Majority baseline"],
                y=[accuracy * 100, baseline * 100],
                marker={"color": [PALETTE[0], "#9ca3af"]},
                text=[f"{accuracy * 100:.1f}%", f"{baseline * 100:.1f}%"],
                textposition="outside",
                hovertemplate="%{x}<br>%{y:.1f}%<extra></extra>",
            )
        ]
    )
    figure.update_layout(yaxis={"title": "Separation rate (%)", "range": [0, max(35, accuracy * 125)]})
    return BuiltFigure(_finalize_figure(figure, spec), spec.caption)


def build_source_effects_by_lens(derived: dict[str, Any], spec: FigureSpec) -> BuiltFigure:
    rows = [_as_dict(row) for row in _as_list(_as_dict(derived.get("source_lens_effects")).get("rows"))]
    rows.sort(key=lambda row: (_num(row.get("eta_sq"), 0) or 0), reverse=True)
    if not rows:
        return _placeholder(spec, "No source lens effect rows available.")
    colors = [PALETTE[0] if row.get("significant_fdr_0_05") else "#94a3b8" for row in rows]
    figure = go.Figure(
        data=[
            go.Bar(
                x=[_num(row.get("eta_sq"), 0) or 0 for row in rows[::-1]],
                y=[_lens_label(row.get("lens")) for row in rows[::-1]],
                orientation="h",
                marker={"color": colors[::-1]},
                text=[f"{(_num(row.get('eta_sq'), 0) or 0):.2f}" for row in rows[::-1]],
                textposition="outside",
                customdata=[[row.get("top_source"), row.get("bottom_source"), row.get("p_value_fdr")] for row in rows[::-1]],
                hovertemplate="Lens: %{y}<br>Effect size: %{x:.3f}<br>Highest mean: %{customdata[0]}<br>Lowest mean: %{customdata[1]}<br>FDR p: %{customdata[2]:.3f}<extra></extra>",
            )
        ]
    )
    figure.update_layout(xaxis={"title": "Source effect size (eta squared)"}, margin={"l": 210, "r": 60, "t": 105, "b": 90})
    return BuiltFigure(_finalize_figure(figure, spec), spec.caption)


def build_event_control_summary(derived: dict[str, Any], spec: FigureSpec) -> BuiltFigure:
    event_control = _as_dict(derived.get("event_control"))
    coverage_rows = [_as_dict(row) for row in _as_list(_as_dict(event_control.get("event_coverage")).get("source_rows"))]
    coverage_rows.sort(key=lambda row: (_num(row.get("multi_source_event_count"), 0) or 0), reverse=True)
    coverage_rows = coverage_rows[:12]
    if not coverage_rows:
        return _placeholder(spec, "No same-event source coverage rows available.")
    figure = go.Figure()
    figure.add_bar(
        x=[_short_label(row.get("source"), 22) for row in coverage_rows],
        y=[_num(row.get("multi_source_event_count"), 0) or 0 for row in coverage_rows],
        name="Shared events",
        marker={"color": PALETTE[1]},
        text=[str(int(_num(row.get("multi_source_event_count"), 0) or 0)) for row in coverage_rows],
        textposition="outside",
    )
    figure.add_scatter(
        x=[_short_label(row.get("source"), 22) for row in coverage_rows],
        y=[(_num(row.get("multi_source_event_article_coverage_ratio"), 0) or 0) * 100 for row in coverage_rows],
        name="Article coverage",
        mode="lines+markers+text",
        text=[f"{((_num(row.get('multi_source_event_article_coverage_ratio'), 0) or 0) * 100):.0f}%" for row in coverage_rows],
        textposition="top center",
        yaxis="y2",
        line={"color": PALETTE[2], "width": 4},
    )
    figure.update_layout(
        yaxis={"title": "Shared event count"},
        yaxis2={"title": "Articles in shared events (%)", "overlaying": "y", "side": "right"},
        xaxis={"tickangle": -30},
    )
    return BuiltFigure(_finalize_figure(figure, spec), spec.caption)


def build_controlled_analysis_coverage(derived: dict[str, Any], spec: FigureSpec) -> BuiltFigure:
    topic_summary = _as_dict(_as_dict(derived.get("source_topic_control")).get("summary"))
    tag_summary = _as_dict(_as_dict(derived.get("tag_sliced_analysis")).get("summary"))
    event_summary = _as_dict(_as_dict(derived.get("event_control")).get("summary"))
    labels = ["Topics", "Tags", "Events"]
    total = [
        _num(topic_summary.get("topic_count"), 0) or 0,
        _num(tag_summary.get("tag_count"), 0) or 0,
        _num(event_summary.get("event_count"), 0) or 0,
    ]
    analyzed = [
        _num(topic_summary.get("analyzed_topic_count"), 0) or 0,
        _num(tag_summary.get("analyzed_tag_count"), 0) or 0,
        _num(event_summary.get("multi_source_event_count"), 0) or 0,
    ]
    if max(total) <= 0:
        return _placeholder(spec, "No controlled-analysis summary available.")
    figure = go.Figure()
    figure.add_bar(x=labels, y=total, name="Available slices", marker={"color": "#94a3b8"}, text=[str(int(v)) for v in total], textposition="outside")
    figure.add_bar(x=labels, y=analyzed, name="Comparable slices", marker={"color": PALETTE[0]}, text=[str(int(v)) for v in analyzed], textposition="outside")
    figure.update_layout(barmode="group", yaxis={"title": "Slice count"})
    return BuiltFigure(_finalize_figure(figure, spec), spec.caption)


def build_article_volume_by_source(derived: dict[str, Any], spec: FigureSpec) -> BuiltFigure:
    rows = _top_mapping_rows(derived.get("source_counts"), label_key="source", limit=16)
    if not rows:
        return _placeholder(spec, "No source-count rows available.")
    figure = go.Figure(
        go.Bar(
            x=[row["count"] for row in rows[::-1]],
            y=[_short_label(row["source"], 32) for row in rows[::-1]],
            orientation="h",
            marker={"color": PALETTE[1]},
            text=[str(int(row["count"])) for row in rows[::-1]],
            textposition="outside",
        )
    )
    figure.update_layout(xaxis={"title": "Article count"}, margin={"l": 230, "r": 60, "t": 105, "b": 90})
    return BuiltFigure(_finalize_figure(figure, spec), spec.caption)


def build_top_tags(derived: dict[str, Any], spec: FigureSpec) -> BuiltFigure:
    rows = _top_mapping_rows(derived.get("tag_counts"), label_key="tag", limit=20)
    if not rows:
        return _placeholder(spec, "No tag-count rows available.")
    figure = go.Figure(
        go.Bar(
            x=[row["count"] for row in rows[::-1]],
            y=[_short_label(row["tag"], 32) for row in rows[::-1]],
            orientation="h",
            marker={"color": PALETTE[0]},
            text=[str(int(row["count"])) for row in rows[::-1]],
            textposition="outside",
        )
    )
    figure.update_layout(xaxis={"title": "Article count"}, margin={"l": 230, "r": 60, "t": 105, "b": 90})
    return BuiltFigure(_finalize_figure(figure, spec), spec.caption)


def build_source_tag_intensity(derived: dict[str, Any], spec: FigureSpec) -> BuiltFigure:
    aggregates = _as_dict(derived.get("chart_aggregates"))
    rows = [_as_dict(row) for row in _as_list(aggregates.get("source_tag_matrix"))]
    top_tags = [row["tag"] for row in _top_mapping_rows(aggregates.get("tag_totals"), label_key="tag", limit=4)]
    source_article_counts = {str(row["source"]): row["count"] for row in _top_mapping_rows(derived.get("source_counts"), label_key="source", limit=999)}
    source_tag_totals = {str(row.get("source")): _num(row.get("count"), 0) or 0 for row in _as_list(aggregates.get("source_tag_totals"))}
    source_sort_counts = source_article_counts or source_tag_totals
    sources = sorted(source_sort_counts, key=lambda source: (-source_sort_counts[source], source))[:6]
    if not rows or not top_tags or not sources:
        return _placeholder(spec, "No source-tag matrix rows available.")
    values: dict[tuple[str, str], float] = {}
    for row in rows:
        source = str(row.get("source") or "")
        tag = str(row.get("tag") or "")
        if source in sources and tag in top_tags:
            count = _num(row.get("count"), 0) or 0
            denominator = source_article_counts.get(source) or source_tag_totals.get(source) or 1
            values[(source, tag)] = count * 100 / denominator
    z = [[values.get((source, tag), 0) for source in sources] for tag in top_tags]
    text = [[f"{value:.0f}%" if value else "" for value in row] for row in z]
    figure = go.Figure(
        go.Heatmap(
            z=z,
            x=[_short_label(source, 22) for source in sources],
            y=[_short_label(tag, 28) for tag in top_tags],
            text=text,
            texttemplate="%{text}",
            textfont={"size": 16, "color": "#111827"},
            colorscale=TAG_INTENSITY_HEATMAP_COLORSCALE,
            colorbar={"title": "Share of<br>source<br>articles"},
            hovertemplate="Source: %{x}<br>Tag: %{y}<br>Share: %{z:.1f}%<extra></extra>",
        )
    )
    figure.update_layout(xaxis={"tickangle": -25, "side": "top"}, yaxis={"title": "Tag", "autorange": "reversed"}, margin={"l": 170, "r": 75, "t": 125, "b": 120})
    return BuiltFigure(_finalize_figure(figure, spec), spec.caption)


def build_score_status_counts(derived: dict[str, Any], spec: FigureSpec) -> BuiltFigure:
    score_status = _as_dict(derived.get("score_status"))
    labels = ["Annotated", "Nonzero", "Zero", "Unusable"]
    values = [
        _num(score_status.get("scored"), 0) or 0,
        _num(score_status.get("positive"), 0) or 0,
        _num(score_status.get("zero"), 0) or 0,
        _num(score_status.get("unscorable"), 0) or 0,
    ]
    if max(values) <= 0:
        return _placeholder(spec, "No score-status counts available.")
    figure = go.Figure(go.Bar(x=labels, y=values, marker={"color": [PALETTE[0], PALETTE[4], "#f59e0b", "#ef4444"]}, text=[str(int(v)) for v in values], textposition="outside"))
    figure.update_layout(yaxis={"title": "Article count"})
    return BuiltFigure(_finalize_figure(figure, spec), spec.caption)


def build_score_status_by_source(derived: dict[str, Any], spec: FigureSpec) -> BuiltFigure:
    rows = [_as_dict(row) for row in _as_list(_as_dict(derived.get("chart_aggregates")).get("score_status_by_source"))]
    rows.sort(key=lambda row: (_num(row.get("total"), 0) or 0), reverse=True)
    rows = rows[:14]
    if not rows:
        return _placeholder(spec, "No per-source score-status rows available.")
    figure = go.Figure()
    for key, label, color in [("scored", "Annotated", PALETTE[0]), ("unscorable", "Unusable", "#ef4444"), ("placeholder_zero_unscorable", "Zero placeholder", "#f59e0b")]:
        figure.add_bar(x=[_short_label(row.get("source"), 24) for row in rows], y=[_num(row.get(key), 0) or 0 for row in rows], name=label, marker={"color": color})
    figure.update_layout(barmode="stack", yaxis={"title": "Article count"}, xaxis={"tickangle": -35})
    return BuiltFigure(_finalize_figure(figure, spec), spec.caption)


def build_daily_article_counts(derived: dict[str, Any], spec: FigureSpec) -> BuiltFigure:
    rows = [_as_dict(row) for row in _as_list(derived.get("daily_counts_utc"))]
    rows = [row for row in rows if row.get("date")]
    if not rows:
        return _placeholder(spec, "No daily article-count rows available.")
    figure = go.Figure(go.Scatter(x=[row.get("date") for row in rows], y=[_num(row.get("count"), 0) or 0 for row in rows], mode="lines+markers", line={"color": PALETTE[0], "width": 4}, fill="tozeroy"))
    figure.update_layout(yaxis={"title": "Article count"}, xaxis={"title": "Date"})
    return BuiltFigure(_finalize_figure(figure, spec), spec.caption)


def build_publish_hour_distribution(derived: dict[str, Any], spec: FigureSpec) -> BuiltFigure:
    rows = [_as_dict(row) for row in _as_list(_as_dict(derived.get("chart_aggregates")).get("publish_hour_counts_utc"))]
    if not rows:
        return _placeholder(spec, "No publish-hour rows available.")
    figure = go.Figure(go.Bar(x=[str(int(_num(row.get("hour"), 0) or 0)).zfill(2) for row in rows], y=[_num(row.get("count"), 0) or 0 for row in rows], marker={"color": PALETTE[1]}))
    figure.update_layout(xaxis={"title": "Publication hour (UTC)"}, yaxis={"title": "Article count"})
    return BuiltFigure(_finalize_figure(figure, spec), spec.caption)


def build_dominant_lens_frequency(derived: dict[str, Any], spec: FigureSpec) -> BuiltFigure:
    counts = _as_dict(_as_dict(derived.get("lens_views")).get("summary")).get("dominant_lens_counts")
    rows = _top_mapping_rows(counts, label_key="lens", limit=15)
    if not rows:
        return _placeholder(spec, "No dominant-lens counts available.")
    figure = go.Figure(
        go.Bar(
            x=[row["count"] for row in rows[::-1]],
            y=[_lens_label(row["lens"]) for row in rows[::-1]],
            orientation="h",
            marker={"color": PALETTE[2]},
            text=[str(int(row["count"])) for row in rows[::-1]],
            textposition="outside",
        )
    )
    figure.update_layout(xaxis={"title": "Article count"}, margin={"l": 210, "r": 60, "t": 105, "b": 90})
    return BuiltFigure(_finalize_figure(figure, spec), spec.caption)


def build_lens_mean_vs_stddev(derived: dict[str, Any], spec: FigureSpec) -> BuiltFigure:
    rows = [_as_dict(row) for row in _as_list(_as_dict(derived.get("lens_views")).get("stability_rows"))]
    rows = [row for row in rows if _num(row.get("mean")) is not None and _num(row.get("stddev")) is not None]
    if not rows:
        return _placeholder(spec, "No lens stability rows available.")
    figure = go.Figure(
        go.Scatter(
            x=[_num(row.get("mean")) for row in rows],
            y=[_num(row.get("stddev")) for row in rows],
            text=[_lens_label(row.get("lens")) for row in rows],
            mode="markers+text",
            textposition="top center",
            marker={"size": [max(10, min(28, math.sqrt(_num(row.get("count"), 1) or 1))) for row in rows], "color": PALETTE[0], "opacity": 0.82},
        )
    )
    figure.update_layout(xaxis={"title": "Mean annotation value"}, yaxis={"title": "Annotation variability"})
    return BuiltFigure(_finalize_figure(figure, spec), spec.caption)


def build_pca_stability(derived: dict[str, Any], spec: FigureSpec) -> BuiltFigure:
    rows = [_as_dict(row) for row in _as_list(_as_dict(derived.get("latent_space_stability")).get("components"))]
    if not rows:
        return _placeholder(spec, "No latent-space stability component rows available.")
    values = [_num(row.get("mean_cosine_similarity"), 0) or 0 for row in rows]
    figure = go.Figure(
        go.Bar(
            x=[str(row.get("component") or "Component") for row in rows],
            y=values,
            marker={"color": [PALETTE[0] if row.get("stable") else "#ef4444" for row in rows]},
            text=[f"{value:.3f}" for value in values],
            textposition="outside",
        )
    )
    figure.update_layout(yaxis={"title": "Mean component similarity", "range": [0, 1.05]})
    return BuiltFigure(_finalize_figure(figure, spec), spec.caption)


def build_pca_loading_variability(derived: dict[str, Any], spec: FigureSpec) -> BuiltFigure:
    rows = [_as_dict(row) for row in _as_list(_as_dict(derived.get("latent_space_stability")).get("loading_stability"))]
    rows.sort(key=lambda row: (_num(row.get("max_loading_stddev"), 0) or 0), reverse=True)
    rows = rows[:12]
    if not rows:
        return _placeholder(spec, "No loading-stability rows available.")
    figure = go.Figure(
        go.Bar(
            x=[_num(row.get("max_loading_stddev"), 0) or 0 for row in rows[::-1]],
            y=[_lens_label(row.get("lens")) for row in rows[::-1]],
            orientation="h",
            marker={"color": PALETTE[3]},
            text=[f"{(_num(row.get('max_loading_stddev'), 0) or 0):.3f}" for row in rows[::-1]],
            textposition="outside",
        )
    )
    figure.update_layout(xaxis={"title": "Maximum loading variability"}, margin={"l": 210, "r": 70, "t": 105, "b": 90})
    return BuiltFigure(_finalize_figure(figure, spec), spec.caption)


def build_daily_lens_scores(derived: dict[str, Any], spec: FigureSpec) -> BuiltFigure:
    series_rows = [_as_dict(row) for row in _as_list(_as_dict(derived.get("lens_time_series")).get("series"))][:6]
    if not series_rows:
        return _placeholder(spec, "No daily lens time-series rows available.")
    figure = go.Figure()
    for index, series in enumerate(series_rows):
        points = [_as_dict(point) for point in _as_list(series.get("points"))]
        figure.add_scatter(
            x=[point.get("date") for point in points],
            y=[_num(point.get("mean"), 0) or 0 for point in points],
            name=_lens_label(series.get("lens")),
            mode="lines+markers",
            line={"color": PALETTE[index % len(PALETTE)], "width": 3},
        )
    figure.update_layout(yaxis={"title": "Mean annotation value", "range": [0, 100]}, xaxis={"title": "Date"})
    return BuiltFigure(_finalize_figure(figure, spec), spec.caption)


def build_daily_lens_scores_reduced(derived: dict[str, Any], spec: FigureSpec) -> BuiltFigure:
    tag_groups = [_as_dict(row) for row in _as_list(_as_dict(_as_dict(derived.get("group_temporal_latent_space")).get("groups")).get("tag"))]
    tag_groups = [
        row
        for row in tag_groups
        if _is_poster_tag_label(row.get("group")) and (_num(row.get("n_buckets"), 0) or 0) >= 2
    ]
    if tag_groups:
        tag_group = sorted(tag_groups, key=lambda row: (-(_num(row.get("n_articles"), 0) or 0), str(row.get("group") or "")))[0]
        buckets = [_as_dict(bucket) for bucket in _as_list(tag_group.get("buckets")) if _as_dict(bucket).get("bucket_start")]
        lens_points: dict[str, list[tuple[str, float]]] = defaultdict(list)
        lens_strength: dict[str, float] = defaultdict(float)
        for bucket in buckets:
            date = str(bucket.get("bucket_start") or "")
            for row in [_as_dict(item) for item in _as_list(bucket.get("top_lens_deviations"))]:
                lens = str(row.get("lens") or "")
                value = _num(row.get("mean_percent"))
                if not lens or value is None:
                    continue
                lens_points[lens].append((date, value))
                lens_strength[lens] += _num(row.get("abs_delta"), 0) or 0
        lenses = sorted(lens_points, key=lambda lens: (-lens_strength[lens], _lens_label(lens)))[:5]
        if lenses:
            figure = go.Figure()
            for index, lens in enumerate(lenses):
                points = sorted(lens_points[lens], key=lambda item: item[0])
                figure.add_scatter(
                    x=[date for date, _value in points],
                    y=[value for _date, value in points],
                    name=_lens_label(lens),
                    mode="lines+markers",
                    line={"color": PALETTE[index % len(PALETTE)], "width": 4},
                    marker={"size": 8},
                )
            figure.add_annotation(
                xref="paper",
                yref="paper",
                x=0.02,
                y=1.04,
                text=f"Tag slice: {_short_label(tag_group.get('group'), 30)} (n={int(_num(tag_group.get('n_articles'), 0) or 0)})",
                showarrow=False,
                align="left",
                font={"size": 18, "color": "#334155"},
            )
            figure.update_layout(yaxis={"title": "Mean annotation value within tag", "range": [0, 100]}, xaxis={"title": "Week"})
            return BuiltFigure(_finalize_figure(figure, spec), spec.caption)

    target_lenses = [
        "Agency and Voice Lens",
        "Authority and Source Positioning Lens",
        "Emotional Intensity Lens",
        "Causal Attribution Lens",
        "Omission and Silence Lens",
    ]
    series_by_lens = {
        str(_as_dict(row).get("lens")): _as_dict(row)
        for row in _as_list(_as_dict(derived.get("lens_time_series")).get("series"))
        if _as_dict(row).get("lens")
    }
    series_rows = [series_by_lens[lens] for lens in target_lenses if lens in series_by_lens]
    if len(series_rows) < 3:
        fallback_rows = [_as_dict(row) for row in _as_list(_as_dict(derived.get("lens_time_series")).get("series"))]
        series_rows = (series_rows + [row for row in fallback_rows if row not in series_rows])[:5]
    else:
        series_rows = series_rows[:5]
    if not series_rows:
        return _placeholder(spec, "No daily lens time-series rows available.")
    figure = go.Figure()
    for index, series in enumerate(series_rows):
        points = [_as_dict(point) for point in _as_list(series.get("points"))]
        figure.add_scatter(
            x=[point.get("date") for point in points],
            y=[_num(point.get("mean"), 0) or 0 for point in points],
            name=_lens_label(series.get("lens")),
            mode="lines+markers",
            line={"color": PALETTE[index % len(PALETTE)], "width": 4},
            marker={"size": 7},
        )
    figure.update_layout(yaxis={"title": "Mean annotation value", "range": [0, 100]}, xaxis={"title": "Date"})
    return BuiltFigure(_finalize_figure(figure, spec), spec.caption)


def build_lens_drift(derived: dict[str, Any], spec: FigureSpec) -> BuiltFigure:
    rows = [_as_dict(row) for row in _as_list(_as_dict(derived.get("drift_diagnostics")).get("lens_drift"))]
    rows.sort(key=lambda row: abs(_num(row.get("delta"), 0) or 0), reverse=True)
    rows = rows[:12]
    if not rows:
        return _placeholder(spec, "No lens-drift rows available.")
    values = [_num(row.get("delta"), 0) or 0 for row in rows[::-1]]
    figure = go.Figure(
        go.Bar(
            x=values,
            y=[_lens_label(row.get("lens")) for row in rows[::-1]],
            orientation="h",
            marker={"color": [PALETTE[0] if value >= 0 else "#ef4444" for value in values]},
            text=[f"{value:+.1f}" for value in values],
            textposition="outside",
        )
    )
    figure.update_layout(xaxis={"title": "Recent minus baseline annotation points"}, margin={"l": 210, "r": 70, "t": 105, "b": 90})
    return BuiltFigure(_finalize_figure(figure, spec), spec.caption)


def build_lens_drift_dumbbell(derived: dict[str, Any], spec: FigureSpec) -> BuiltFigure:
    rows = [_as_dict(row) for row in _as_list(_as_dict(derived.get("drift_diagnostics")).get("lens_drift"))]
    rows = [
        row
        for row in rows
        if _num(row.get("baseline_mean")) is not None and _num(row.get("recent_mean")) is not None
    ]
    rows.sort(key=lambda row: abs(_num(row.get("delta"), 0) or 0), reverse=True)
    rows = rows[:8]
    if not rows:
        return _placeholder(spec, "No baseline/recent lens-drift rows available.")

    ordered = rows[::-1]
    y_labels = [_lens_label(row.get("lens")) for row in ordered]
    baseline_values = [_num(row.get("baseline_mean"), 0) or 0 for row in ordered]
    recent_values = [_num(row.get("recent_mean"), 0) or 0 for row in ordered]
    deltas = [_num(row.get("delta"), 0) or 0 for row in ordered]
    figure = go.Figure()
    for index, row in enumerate(ordered):
        color = "#047857" if deltas[index] >= 0 else "#7e22ce"
        figure.add_scatter(
            x=[baseline_values[index], recent_values[index]],
            y=[y_labels[index], y_labels[index]],
            mode="lines",
            line={"color": color, "width": 5},
            showlegend=False,
            hoverinfo="skip",
        )
        figure.add_annotation(
            x=recent_values[index],
            y=y_labels[index],
            text=f"{deltas[index]:+.1f}",
            showarrow=False,
            xshift=34 if deltas[index] >= 0 else -34,
            font={"size": 15, "color": color},
            bgcolor="rgba(255,255,255,0.75)",
        )
    figure.add_scatter(
        x=baseline_values,
        y=y_labels,
        mode="markers",
        name="Baseline",
        marker={"size": 15, "color": "#94a3b8", "line": {"color": "#475569", "width": 1}},
        hovertemplate="Baseline<br>%{y}: %{x:.1f}<extra></extra>",
    )
    figure.add_scatter(
        x=recent_values,
        y=y_labels,
        mode="markers",
        name="Recent",
        marker={"size": 17, "color": "#111827", "line": {"color": "white", "width": 1.5}},
        hovertemplate="Recent<br>%{y}: %{x:.1f}<extra></extra>",
    )
    figure.add_annotation(
        xref="paper",
        yref="paper",
        x=0,
        y=1.05,
        text="Line color: green = recent higher, purple = recent lower.",
        showarrow=False,
        align="left",
        font={"size": 16, "color": "#475569"},
    )
    finalized = _finalize_figure(figure, spec)
    finalized.update_layout(
        xaxis={"title": "Mean annotation value", "range": [0, 105]},
        yaxis={"title": ""},
        margin={"l": 260, "r": 105, "t": 70, "b": 95},
        legend={"orientation": "h", "x": 0, "y": -0.18},
    )
    return BuiltFigure(finalized, spec.caption)


def build_distribution_share_shifts(derived: dict[str, Any], spec: FigureSpec) -> BuiltFigure:
    drift = _as_dict(derived.get("drift_diagnostics"))
    source_rows = [_as_dict(row) for row in _as_list(_as_dict(drift.get("source_distribution_drift")).get("rows"))]
    tag_rows = [_as_dict(row) for row in _as_list(_as_dict(drift.get("tag_distribution_drift")).get("rows"))]
    source_rows.sort(key=lambda row: abs(_num(row.get("share_delta"), 0) or 0), reverse=True)
    tag_rows.sort(key=lambda row: abs(_num(row.get("share_delta"), 0) or 0), reverse=True)
    rows = [
        {"label": f"S: {_short_label(row.get('source'), 24)}", "delta": (_num(row.get("share_delta"), 0) or 0) * 100}
        for row in source_rows[:8]
    ] + [
        {"label": f"T: {_short_label(row.get('tag'), 24)}", "delta": (_num(row.get("share_delta"), 0) or 0) * 100}
        for row in tag_rows[:8]
    ]
    rows.sort(key=lambda row: abs(row["delta"]), reverse=True)
    if not rows:
        return _placeholder(spec, "No source/tag share-shift rows available.")
    values = [row["delta"] for row in rows[::-1]]
    figure = go.Figure(
        go.Bar(
            x=values,
            y=[row["label"] for row in rows[::-1]],
            orientation="h",
            marker={"color": [PALETTE[0] if value >= 0 else "#ef4444" for value in values]},
            text=[f"{value:+.1f}" for value in values],
            textposition="outside",
        )
    )
    figure.update_layout(xaxis={"title": "Recent minus baseline share (percentage points)"}, margin={"l": 260, "r": 75, "t": 105, "b": 90})
    return BuiltFigure(_finalize_figure(figure, spec), spec.caption)


def build_focus_lens_source_means(derived: dict[str, Any], spec: FigureSpec) -> BuiltFigure:
    rows = [_as_dict(row) for row in _as_list(_as_dict(derived.get("source_lens_effects")).get("rows"))]
    rows.sort(key=lambda row: (_num(row.get("eta_sq"), 0) or 0), reverse=True)
    focus = rows[0] if rows else {}
    means = _as_dict(focus.get("source_means"))
    counts = _as_dict(focus.get("source_counts"))
    source_rows = [
        {"source": source, "mean": _num(mean, 0) or 0, "count": _num(counts.get(source), 0) or 0}
        for source, mean in means.items()
    ]
    source_rows.sort(key=lambda row: row["mean"], reverse=True)
    if not source_rows:
        return _placeholder(spec, "No source means available for focus lens.")
    figure = go.Figure(
        go.Bar(
            x=[_short_label(row["source"], 24) for row in source_rows],
            y=[row["mean"] for row in source_rows],
            marker={"color": PALETTE[1]},
            text=[f"{row['mean']:.0f}<br>n={int(row['count'])}" for row in source_rows],
            textposition="outside",
        )
    )
    figure.update_layout(
        title={"text": f"Source Annotation Means: {_lens_label(focus.get('lens'))}", "x": 0.02, "xanchor": "left", "font": {"size": 28}},
        yaxis={"title": "Mean annotation value", "range": [0, 105]},
        xaxis={"tickangle": -35},
    )
    return BuiltFigure(_finalize_figure(figure, spec), spec.caption)


def _plurality_article_weight(row: dict[str, Any], target_lenses: list[str]) -> tuple[float, str]:
    title = str(row.get("title") or "")
    lower_title = title.casefold()
    if any(term in lower_title for term in PLURALITY_TITLE_REJECT_TERMS):
        return (-1.0, title)

    scores = _as_dict(row.get("lens_scores"))
    lens_values = [_num(scores.get(lens)) for lens in target_lenses]
    lens_values = [value for value in lens_values if value is not None]
    if len(lens_values) < 4:
        return (-1.0, title)

    causality = _num(scores.get("Causal Attribution Lens"), 0) or 0
    if causality < 15:
        return (-1.0, title)

    spread = max(lens_values) - min(lens_values)
    weight = spread + min(causality, 75) * 0.35
    if 55 <= len(title) <= 115:
        weight += 10
    if (_num(scores.get("Emotional Intensity Lens"), 0) or 0) >= 20:
        weight += 8

    weight += sum(22 for term in PLURALITY_TITLE_PREFERRED_TERMS if term in lower_title)
    weight -= sum(22 for term in PLURALITY_TITLE_DOWNRANK_TERMS if term in lower_title)
    return (weight, title)


def build_lens_plurality_panel(derived: dict[str, Any], spec: FigureSpec) -> BuiltFigure:
    article_rows = [_as_dict(row) for row in _as_list(_as_dict(derived.get("lens_views")).get("article_rows"))]
    target_lenses = list(LENS_PLURALITY_RUBRICS)
    candidates: list[tuple[float, str, dict[str, Any]]] = []
    for row in article_rows:
        weight, title = _plurality_article_weight(row, target_lenses)
        if weight >= 0:
            candidates.append((weight, title, row))
    if not candidates:
        return _placeholder(spec, "No article-level lens rows available for plurality panel.")
    article = max(candidates, key=lambda item: (item[0], item[1]))[2]
    scores = _as_dict(article.get("lens_scores"))
    center_text = (
        f"<b>{_wrap_text(article.get('title'), 34, 3)}</b><br>"
        f"{_short_label(article.get('source'), 30)}"
    )
    positions = [
        (0.5, 0.84),
        (0.82, 0.62),
        (0.82, 0.28),
        (0.5, 0.10),
        (0.18, 0.28),
        (0.18, 0.62),
    ]
    figure = go.Figure()
    figure.update_xaxes(visible=False, range=[0, 1])
    figure.update_yaxes(visible=False, range=[-0.06, 1.04])
    figure.add_shape(type="circle", x0=0.36, x1=0.64, y0=0.36, y1=0.64, fillcolor="#f8fafc", line={"color": "#334155", "width": 2.5}, layer="below")
    figure.add_annotation(x=0.5, y=0.5, text=center_text, showarrow=False, align="center", font={"size": 22, "color": "#111827"})
    for index, lens in enumerate(target_lenses):
        x, y = positions[index]
        score = _num(scores.get(lens), 0) or 0
        fill = "#f3e8ff" if score < 50 else "#dcfce7"
        border = "#7e22ce" if score < 50 else "#166534"
        radius_x = 0.12
        radius_y = 0.12
        figure.add_shape(type="line", x0=0.5, y0=0.5, x1=x, y1=y, line={"color": "#cbd5e1", "width": 2}, layer="below")
        figure.add_shape(type="circle", x0=x - radius_x, x1=x + radius_x, y0=y - radius_y, y1=y + radius_y, fillcolor=fill, line={"color": border, "width": 2.5}, layer="below")
        phrase = _quote_wrapped_question(LENS_POSTER_CUES.get(lens, _lens_label(lens)), 26, 2)
        text = f"<b>{_lens_label(lens)}</b><br>Value {score:.0f}<br><i>{phrase}</i>"
        figure.add_annotation(x=x, y=y, text=text, showarrow=False, align="center", font={"size": 18, "color": "#111827"})
    figure.update_layout(margin={"l": 35, "r": 35, "t": 55, "b": 35})
    return BuiltFigure(_finalize_figure(figure, spec), spec.caption)


def _merged_display_counts(mapping: dict[str, Any]) -> dict[str, float]:
    merged: dict[str, tuple[str, float]] = {}
    for label, count in mapping.items():
        display = str(label or "").strip()
        if not display:
            continue
        key = display.casefold()
        current_display, current_count = merged.get(key, (display, 0.0))
        next_count = current_count + (_num(count, 0) or 0)
        # Prefer title case/display-rich labels when duplicates differ only by case.
        if len(display) > len(current_display) or current_display.islower():
            current_display = display
        merged[key] = (current_display, next_count)
    return {display: count for display, count in merged.values()}


def _event_interpretive_weight(event: dict[str, Any]) -> tuple[float, float, str]:
    tags = _merged_display_counts(_as_dict(event.get("tag_counts")))
    title = str(event.get("representative_title") or "")
    text = " ".join([title, *tags.keys()]).casefold()
    article_count = _num(event.get("article_count"), 0) or 0
    source_count = len(_as_list(event.get("sources"))) or len(_as_dict(event.get("source_counts")))
    preferred_terms = (
        "iran",
        "israel",
        "ceasefire",
        "congress",
        "white house",
        "politics",
        "court",
        "security",
        "diplomacy",
        "election",
        "economy",
        "tariff",
        "trade",
        "human rights",
        "conflict",
    )
    downrank_terms = ("sports", "marathon", "obituary", "entertainment", "celebrity")
    semantic_score = sum(4.0 for term in preferred_terms if term in text)
    semantic_score -= sum(5.0 for term in downrank_terms if term in text)
    coverage_score = article_count + source_count * 1.5
    return (semantic_score, coverage_score, title)


def build_event_plurality_panel(derived: dict[str, Any], spec: FigureSpec) -> BuiltFigure:
    events = [_as_dict(row) for row in _as_list(_as_dict(derived.get("event_control")).get("events"))]
    events = [event for event in events if (_num(event.get("article_count"), 0) or 0) >= 2 and len(_as_list(event.get("sources"))) >= 2]
    if not events:
        return _placeholder(spec, "No multi-source event clusters available for event plurality panel.")
    event = max(events, key=_event_interpretive_weight)
    source_counts = _as_dict(event.get("source_counts"))
    tag_counts = _merged_display_counts(_as_dict(event.get("tag_counts")))
    sources = _as_list(event.get("sources")) or sorted(source_counts)
    top_tags = sorted(tag_counts.items(), key=lambda item: (-(_num(item[1], 0) or 0), str(item[0])))[:4]
    source_summary = ", ".join(_short_label(source, 16) for source in sources[:3])
    tag_summary = ", ".join(_short_label(tag, 20) for tag, _count in top_tags[:3])
    article_count = int(_num(event.get("article_count"), 0) or 0)
    article_ids = _as_list(event.get("article_ids"))
    date_start = event.get("date_start") or "date unknown"
    date_end = event.get("date_end") or date_start
    date_label = str(date_start) if date_start == date_end else f"{date_start} to {date_end}"
    center_text = (
        f"<b>{_wrap_text(event.get('representative_title'), 30, 3)}</b><br>"
        f"{date_label}<br>"
        f"{article_count} articles / {len(sources)} sources"
    )
    panels = [
        ("Source spread", source_summary or "Multiple sources", "shared coverage"),
        ("Rhetorical tags", tag_summary or "No dominant tags", "close reading cues"),
        ("Coverage window", date_label, f"{article_count} articles / {len(sources)} sources"),
        ("Inspectable trail", f"{len(article_ids) or article_count} source records", "traceable"),
    ]
    positions = [(0.5, 0.80), (0.84, 0.50), (0.5, 0.20), (0.16, 0.50)]
    figure = go.Figure()
    figure.update_xaxes(visible=False, range=[0, 1])
    figure.update_yaxes(visible=False, range=[0, 1])
    figure.add_shape(type="circle", x0=0.33, x1=0.67, y0=0.36, y1=0.64, fillcolor="#f8fafc", line={"color": "#334155", "width": 3}, layer="below")
    figure.add_annotation(x=0.5, y=0.5, text=center_text, showarrow=False, align="center", font={"size": 27, "color": "#111827"})
    for index, ((heading, value, phrase), (x, y)) in enumerate(zip(panels, positions)):
        radius = 0.145
        figure.add_shape(type="line", x0=0.5, y0=0.5, x1=x, y1=y, line={"color": "#cbd5e1", "width": 2.5}, layer="below")
        figure.add_shape(
            type="circle",
            x0=x - radius,
            x1=x + radius,
            y0=y - radius,
            y1=y + radius,
            fillcolor=["#ecfeff", "#fef3c7", "#f3e8ff", "#dcfce7"][index],
            line={"color": ["#0e7490", "#b45309", "#7e22ce", "#166534"][index], "width": 3},
            layer="below",
        )
        text = f"<b>{heading}</b><br>{_wrap_text(value, 24, 2)}<br><i>{_wrap_text(phrase, 22, 2)}</i>"
        figure.add_annotation(x=x, y=y, text=text, showarrow=False, align="center", font={"size": 25, "color": "#111827"})
    figure.update_layout(margin={"l": 35, "r": 35, "t": 55, "b": 35})
    return BuiltFigure(_finalize_figure(figure, spec), spec.caption)


def _topic_lens_weighted_means(topic: dict[str, Any]) -> dict[str, float]:
    rows = [_as_dict(row) for row in _as_list(_as_dict(topic.get("source_lens_effects")).get("rows"))]
    means: dict[str, float] = {}
    for row in rows:
        lens = str(row.get("lens") or "")
        source_means = _as_dict(row.get("source_means"))
        source_counts = _as_dict(row.get("source_counts"))
        weighted_total = 0.0
        count_total = 0.0
        for source, mean in source_means.items():
            count = _num(source_counts.get(source), 0) or 0
            value = _num(mean)
            if count <= 0 or value is None:
                continue
            weighted_total += value * count
            count_total += count
        if lens and count_total > 0:
            means[lens] = weighted_total / count_total
    return means


def _lens_summary_means(payload: dict[str, Any]) -> dict[str, float]:
    rows = [_as_dict(row) for row in _as_list(_as_dict(payload.get("lens_summary")).get("lenses"))]
    return {
        str(row.get("lens")): _num(row.get("mean_percent"), 0) or 0
        for row in rows
        if row.get("lens")
    }


def _tag_slice_rows(derived: dict[str, Any]) -> list[dict[str, Any]]:
    rows = [_as_dict_or_literal(row) for row in _as_list(_as_dict(derived.get("tag_sliced_analysis")).get("tags"))]
    return [row for row in rows if row]


def _is_poster_tag_label(value: Any) -> bool:
    label = str(value or "").strip()
    if not label:
        return False
    generic = {"__untagged__", "untagged", "world", "news", "latest", "live"}
    return label.casefold() not in generic


def _tag_lens_pca_profile_rows(derived: dict[str, Any]) -> list[dict[str, Any]]:
    rows = [_as_dict(row) for row in _as_list(_as_dict(derived.get("tag_lens_pca")).get("tag_points"))]
    profiles: list[dict[str, Any]] = []
    for row in rows:
        lens_means = {
            str(lens): _num(value, 0) or 0
            for lens, value in _as_dict(row.get("lens_means")).items()
            if lens
        }
        tag = str(row.get("tag") or "")
        if not lens_means or not _is_poster_tag_label(tag):
            continue
        profiles.append(
            {
                "tag": tag,
                "n_articles": _num(row.get("n_articles"), 0) or 0,
                "lens_summary": {
                    "lenses": [
                        {"lens": lens, "mean_percent": value}
                        for lens, value in lens_means.items()
                    ]
                },
            }
        )
    profiles.sort(key=lambda row: (-(_num(row.get("n_articles"), 0) or 0), str(row.get("tag") or "")))
    return profiles


def _tag_profile_divergence_rows(derived: dict[str, Any], corpus_means: dict[str, float | None], limit: int = 4) -> list[dict[str, Any]]:
    rows = []
    profiles = [profile for profile in _tag_lens_pca_profile_rows(derived) if (_num(profile.get("n_articles"), 0) or 0) >= 20]
    if len(profiles) < limit:
        profiles = _tag_lens_pca_profile_rows(derived)
    for profile in profiles:
        means = _lens_summary_means(profile)
        deltas = {
            lens: means[lens] - corpus_mean
            for lens, corpus_mean in corpus_means.items()
            if corpus_mean is not None and lens in means
        }
        if not deltas:
            continue
        rows.append(
            {
                "topic": f"Tag: {profile.get('tag') or 'Tag'}",
                "n_articles": _num(profile.get("n_articles"), 0) or 0,
                "deltas": deltas,
                "overall": sum(abs(value) for value in deltas.values()) / len(deltas),
            }
        )
    rows.sort(key=lambda row: (-row["overall"], -min(row["n_articles"], 60), row["topic"]))
    return rows[:limit]


def _profile_distance(first: dict[str, float], second: dict[str, float]) -> float:
    shared = set(first) & set(second)
    if not shared:
        return 0.0
    return math.sqrt(sum((first[lens] - second[lens]) ** 2 for lens in shared) / len(shared))


def _select_two_tag_slices(derived: dict[str, Any]) -> list[dict[str, Any]]:
    rows = [row for row in _tag_slice_rows(derived) if _is_poster_tag_label(row.get("tag"))]
    if len(rows) < 2:
        rows = _tag_lens_pca_profile_rows(derived)
    if len(rows) < 2:
        return rows[:2]
    candidates = [row for row in rows if (_num(row.get("n_articles"), 0) or 0) >= 10]
    if len(candidates) < 2:
        candidates = rows
    best_pair: tuple[float, dict[str, Any], dict[str, Any]] | None = None
    for index, first in enumerate(candidates):
        first_means = _lens_summary_means(first)
        for second in candidates[index + 1:]:
            second_means = _lens_summary_means(second)
            distance = _profile_distance(first_means, second_means)
            if distance <= 0:
                continue
            coverage = math.log((_num(first.get("n_articles"), 0) or 0) + (_num(second.get("n_articles"), 0) or 0) + 1)
            score = distance * coverage
            if best_pair is None or score > best_pair[0]:
                best_pair = (score, first, second)
    if best_pair is None:
        return candidates[:2]
    first, second = best_pair[1], best_pair[2]
    return sorted([first, second], key=lambda row: (-(_num(row.get("n_articles"), 0) or 0), str(row.get("tag") or "")))


def _tag_comparison_lenses(means_by_tag: list[tuple[str, float, dict[str, float]]], limit: int = 6) -> list[str]:
    if len(means_by_tag) < 2:
        return []
    common = set(means_by_tag[0][2])
    for _label, _count, means in means_by_tag[1:]:
        common &= set(means)
    ranked = sorted(
        common,
        key=lambda lens: abs((means_by_tag[0][2].get(lens, 0) or 0) - (means_by_tag[1][2].get(lens, 0) or 0)),
        reverse=True,
    )
    return ranked[:limit]


def build_two_tag_lens_comparison(derived: dict[str, Any], spec: FigureSpec) -> BuiltFigure:
    selected_tags = _select_two_tag_slices(derived)
    if len(selected_tags) < 2:
        return _placeholder(spec, "Need at least two tag slices for comparison.")
    means_by_tag = [(str(row.get("tag") or "Tag"), _num(row.get("n_articles"), 0) or 0, _lens_summary_means(row)) for row in selected_tags]
    lenses = sorted(set(means_by_tag[0][2]) & set(means_by_tag[1][2]), key=lambda lens: abs((means_by_tag[0][2].get(lens, 0) or 0) - (means_by_tag[1][2].get(lens, 0) or 0)), reverse=True)[:8]
    if not lenses:
        return _placeholder(spec, "Selected tag slices do not share lens summaries.")
    first_label, first_count, first_means = means_by_tag[0]
    second_label, second_count, second_means = means_by_tag[1]
    figure = go.Figure()
    figure.add_bar(
        x=[_lens_label(lens) for lens in lenses],
        y=[first_means.get(lens, 0) for lens in lenses],
        name=f"{_short_label(first_label, 24)} (n={int(first_count)})",
        marker={"color": PALETTE[0]},
        text=[f"{first_means.get(lens, 0):.0f}" for lens in lenses],
        textposition="outside",
    )
    figure.add_bar(
        x=[_lens_label(lens) for lens in lenses],
        y=[second_means.get(lens, 0) for lens in lenses],
        name=f"{_short_label(second_label, 24)} (n={int(second_count)})",
        marker={"color": PALETTE[3]},
        text=[f"{second_means.get(lens, 0):.0f}" for lens in lenses],
        textposition="outside",
    )
    figure.update_layout(
        barmode="group",
        yaxis={"title": "Mean annotation value", "range": [0, 105]},
        xaxis={"tickangle": -25},
        legend={"orientation": "h", "y": -0.18, "x": 0},
        margin={"l": 90, "r": 55, "t": 80, "b": 155},
    )
    return BuiltFigure(_finalize_figure(figure, spec), spec.caption)


def build_two_tag_lens_fingerprints(derived: dict[str, Any], spec: FigureSpec) -> BuiltFigure:
    selected_tags = _select_two_tag_slices(derived)
    if len(selected_tags) < 2:
        return _placeholder(spec, "Need at least two tag slices for lens fingerprints.")
    means_by_tag = [(str(row.get("tag") or "Tag"), _num(row.get("n_articles"), 0) or 0, _lens_summary_means(row)) for row in selected_tags]
    lenses = _tag_comparison_lenses(means_by_tag, limit=6)
    if len(lenses) < 3:
        return _placeholder(spec, "Selected tag slices do not share enough lens summaries.")
    theta = [_lens_label(lens) for lens in lenses] + [_lens_label(lenses[0])]
    figure = go.Figure()
    for index, (label, count, means) in enumerate(means_by_tag[:2]):
        values = [means.get(lens, 0) for lens in lenses]
        figure.add_trace(
            go.Scatterpolar(
                r=values + [values[0]],
                theta=theta,
                fill="toself",
                name=f"{_short_label(label, 20)} (n={int(count)})",
                line={"color": PALETTE[index * 3 % len(PALETTE)], "width": 4},
                marker={"size": 8},
                opacity=0.72,
                hovertemplate="%{theta}<br>%{r:.1f}<extra></extra>",
            )
        )
    figure.add_annotation(
        xref="paper",
        yref="paper",
        x=0.5,
        y=1.04,
        text="The same interpretive questions produce different reading profiles across tags.",
        showarrow=False,
        align="center",
        font={"size": 18, "color": "#334155"},
    )
    finalized = _finalize_figure(figure, spec)
    finalized.update_layout(
        polar={
            "bgcolor": "#fffaf0",
            "radialaxis": {"visible": True, "range": [0, 100], "tickfont": {"size": 13}, "gridcolor": "#cbd5e1"},
            "angularaxis": {"tickfont": {"size": 15}, "gridcolor": "#cbd5e1"},
        },
        legend={"orientation": "h", "x": 0.12, "y": -0.08, "font": {"size": 18}},
        margin={"l": 90, "r": 90, "t": 90, "b": 90},
    )
    return BuiltFigure(finalized, spec.caption)


def build_topic_lens_divergence(derived: dict[str, Any], spec: FigureSpec) -> BuiltFigure:
    stability_rows = [_as_dict(row) for row in _as_list(_as_dict(derived.get("lens_views")).get("stability_rows"))]
    corpus_means = {str(row.get("lens")): _num(row.get("mean")) for row in stability_rows if row.get("lens")}
    topics = [_as_dict(row) for row in _as_list(_as_dict(derived.get("source_topic_control")).get("topics"))]
    topic_rows = []
    for topic in topics:
        if str(topic.get("topic") or "") == "Untagged":
            continue
        means = _topic_lens_weighted_means(topic)
        deltas = {
            lens: means[lens] - corpus_mean
            for lens, corpus_mean in corpus_means.items()
            if corpus_mean is not None and lens in means
        }
        if not deltas:
            continue
        topic_rows.append(
            {
                "topic": str(topic.get("topic") or "Topic"),
                "n_articles": _num(topic.get("n_articles"), 0) or 0,
                "deltas": deltas,
                "overall": sum(abs(value) for value in deltas.values()) / len(deltas),
            }
        )
    if not topic_rows:
        tag_rows = [_as_dict_or_literal(row) for row in _as_list(_as_dict(derived.get("tag_sliced_analysis")).get("tags"))]
        for tag in tag_rows:
            if not _is_poster_tag_label(tag.get("tag")):
                continue
            means = _lens_summary_means(tag)
            deltas = {
                lens: means[lens] - corpus_mean
                for lens, corpus_mean in corpus_means.items()
                if corpus_mean is not None and lens in means
            }
            if not deltas:
                continue
            topic_rows.append(
                {
                    "topic": f"Tag: {tag.get('tag') or 'Tag'}",
                    "n_articles": _num(tag.get("n_articles"), 0) or 0,
                    "deltas": deltas,
                    "overall": sum(abs(value) for value in deltas.values()) / len(deltas),
                }
            )
    if len(topic_rows) < 3:
        existing = {row["topic"].casefold() for row in topic_rows}
        for row in _tag_profile_divergence_rows(derived, corpus_means, limit=5):
            if row["topic"].casefold() not in existing:
                topic_rows.append(row)
                existing.add(row["topic"].casefold())
            if len(topic_rows) >= 4:
                break
    available_lenses = {lens for row in topic_rows for lens in row["deltas"]}
    lenses = [lens for lens, _description in INTERPRETABLE_DIVERGENCE_LENSES if lens in available_lenses]
    if len(lenses) < 3:
        fallback = sorted(available_lenses - set(lenses), key=lambda lens: _lens_label(lens))
        lenses.extend(fallback[: max(0, 6 - len(lenses))])
    lenses = lenses[:6]
    scoped_rows = []
    for row in topic_rows:
        scoped_deltas = {lens: row["deltas"][lens] for lens in lenses if lens in row["deltas"]}
        if not scoped_deltas:
            continue
        scoped_rows.append(
            {
                **row,
                "deltas": scoped_deltas,
                "overall": sum(abs(value) for value in scoped_deltas.values()) / len(scoped_deltas),
            }
        )
    topic_rows = sorted(scoped_rows, key=lambda row: (-row["overall"], -row["n_articles"], row["topic"]))[:4]
    if not topic_rows or not lenses:
        return _placeholder(spec, "No topic-level lens divergence rows available.")
    lens_key = dict(INTERPRETABLE_DIVERGENCE_LENSES)
    x_labels = [_lens_label(lens).replace(" / ", "<br>") for lens in lenses]
    y_labels = [f"{_short_label(row['topic'], 26)}<br>n={int(row['n_articles'])}" for row in topic_rows]
    z = [
        [row["deltas"].get(lens, 0) for lens in lenses]
        for row in topic_rows
    ]
    values = [value for row in z for value in row]
    max_abs = max((abs(value) for value in values), default=1.0)
    text = [[f"{value:+.1f}" for value in row] for row in z]
    figure = go.Figure(
        go.Heatmap(
            z=z,
            x=x_labels,
            y=y_labels,
            text=text,
            texttemplate="%{text}",
            textfont={"size": 15, "color": "#111827"},
            colorscale=[
                [0.0, "#7c2d12"],
                [0.22, "#d97706"],
                [0.48, "#fff7ed"],
                [0.52, "#f0fdfa"],
                [0.78, "#0f766e"],
                [1.0, "#042f2e"],
            ],
            zmid=0,
            zmin=-max_abs,
            zmax=max_abs,
            colorbar={
                "title": {"text": "Annotation<br>delta", "font": {"size": 22}},
                "tickfont": {"size": 18},
                "len": 0.72,
            },
            hovertemplate="Slice: %{y}<br>Lens: %{x}<br>Delta from corpus mean: %{z:.1f}<extra></extra>",
        )
    )
    key_lines = [
        f"<b>{_lens_label(lens)}</b>: {lens_key.get(lens, 'Rubric-mediated reading')}"
        for lens in lenses
    ]
    key_columns = [
        " &nbsp; ".join(key_lines[index : index + 2])
        for index in range(0, len(key_lines), 2)
    ]
    figure.add_annotation(
        text="Positive cells mean stronger rubric agreement than the corpus average; negative cells mean weaker agreement.",
        x=0,
        y=1.16,
        xref="paper",
        yref="paper",
        showarrow=False,
        align="left",
        font={"size": 24, "color": "#374151"},
    )
    figure.add_annotation(
        text="<br>".join(key_columns),
        x=0,
        y=-0.24,
        xref="paper",
        yref="paper",
        showarrow=False,
        align="left",
        font={"size": 21, "color": "#374151"},
    )
    figure.update_layout(xaxis={"tickangle": 0, "side": "top"}, yaxis={"autorange": "reversed"})
    finalized = _finalize_figure(figure, spec)
    finalized.update_layout(
        margin={"l": 265, "r": 130, "t": 180, "b": 280},
        font={"family": "Arial, Helvetica, sans-serif", "size": 22, "color": "#172033"},
    )
    finalized.update_traces(textfont={"size": 22, "color": "#111827"}, selector={"type": "heatmap"})
    finalized.update_xaxes(tickfont={"size": 24}, title_font={"size": 24})
    finalized.update_yaxes(tickfont={"size": 24}, title_font={"size": 24})
    return BuiltFigure(finalized, spec.caption)


BUILDERS: dict[str, Builder] = {
    "source_lens_matrix": build_source_lens_matrix,
    "lens_correlation_heatmap": build_lens_correlation_heatmap,
    "lens_pca_variance": build_lens_pca_variance,
    "article_pca_source_space": build_article_pca_source_space,
    "article_mds_source_space": build_article_mds_source_space,
    "tag_lens_pca_clusters": build_tag_lens_pca_clusters,
    "discourse_constellation": build_discourse_constellation,
    "group_latent_source_centroids": build_group_latent_source_centroids,
    "tag_momentum": build_tag_momentum,
    "temporal_centroid_path": build_temporal_centroid_path,
    "source_differentiation": build_source_differentiation,
    "source_effects_by_lens": build_source_effects_by_lens,
    "event_control_summary": build_event_control_summary,
    "controlled_analysis_coverage": build_controlled_analysis_coverage,
    "article_volume_by_source": build_article_volume_by_source,
    "top_tags": build_top_tags,
    "source_tag_intensity": build_source_tag_intensity,
    "score_status_counts": build_score_status_counts,
    "score_status_by_source": build_score_status_by_source,
    "daily_article_counts": build_daily_article_counts,
    "publish_hour_distribution": build_publish_hour_distribution,
    "dominant_lens_frequency": build_dominant_lens_frequency,
    "lens_mean_vs_stddev": build_lens_mean_vs_stddev,
    "pca_stability": build_pca_stability,
    "pca_loading_variability": build_pca_loading_variability,
    "daily_lens_scores": build_daily_lens_scores,
    "daily_lens_scores_reduced": build_daily_lens_scores_reduced,
    "lens_drift": build_lens_drift,
    "lens_drift_dumbbell": build_lens_drift_dumbbell,
    "distribution_share_shifts": build_distribution_share_shifts,
    "focus_lens_source_means": build_focus_lens_source_means,
    "lens_plurality_panel": build_lens_plurality_panel,
    "event_plurality_panel": build_event_plurality_panel,
    "topic_lens_divergence": build_topic_lens_divergence,
    "two_tag_lens_comparison": build_two_tag_lens_comparison,
    "two_tag_lens_fingerprints": build_two_tag_lens_fingerprints,
}


def load_stats_payload(*, stats_url: str | None = None, stats_json: Path | None = None) -> dict[str, Any]:
    if stats_json is not None:
        return json.loads(stats_json.read_text(encoding="utf-8"))
    url = stats_url or DEFAULT_STATS_URL
    with urllib.request.urlopen(url, timeout=60) as response:
        return json.loads(response.read().decode("utf-8"))


def stats_derived(payload: dict[str, Any]) -> dict[str, Any]:
    return _as_dict(_as_dict(payload.get("data")).get("derived"))


def build_figure(derived: dict[str, Any], spec: FigureSpec) -> BuiltFigure:
    available, reason = _required_available(derived, spec)
    if not available:
        return _placeholder(spec, reason)
    builder = BUILDERS.get(spec.builder)
    if builder is None:
        return _placeholder(spec, f"Unknown builder: {spec.builder}")
    try:
        return builder(derived, spec)
    except Exception as exc:  # pragma: no cover - defensive export resilience
        return _placeholder(spec, f"{type(exc).__name__}: {exc}")


def merge_pdfs(pdf_paths: list[Path], output_path: Path) -> None:
    from pypdf import PdfWriter

    writer = PdfWriter()
    for path in pdf_paths:
        writer.append(str(path))
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("wb") as output_file:
        writer.write(output_file)


def write_readme(output_dir: Path, manifest: dict[str, Any]) -> None:
    lines = [
        "# NewsLens Poster Figure Exports",
        "",
        f"Generated at: {manifest['generated_at']}",
        f"Source: {manifest['source']}",
        "",
        "These figures are vector exports generated from backend stats data, not browser screenshots.",
        "Treat lens values as computational annotations that support comparative reading and keep control-mode labels visible in poster copy.",
        "",
        "## Figures",
        "",
    ]
    for figure in manifest["figures"]:
        lines.extend(
            [
                f"### {figure['id']}: {figure['title']}",
                "",
                f"- Status: {figure['status']}",
                f"- Figure label: {figure['caption']}",
                f"- Method: {figure.get('method', '')}",
                f"- Encoding: {figure.get('encoding', '')}",
                f"- Interpretive note: {figure.get('interpretive_note', '')}",
                f"- SVG: `{figure['svg']}`",
                f"- PDF: `{figure['pdf']}`",
                "",
            ]
        )
    output_dir.joinpath("README.md").write_text("\n".join(lines), encoding="utf-8")


def narrative_poster_sections(manifest: dict[str, Any]) -> str:
    figure_lookup = {figure["id"]: figure for figure in manifest["figures"]}
    order = [
        "29_lens_plurality_panel",
        "31_event_plurality_panel",
        "02_lens_correlation_heatmap",
        "06_tag_lens_pca_clusters",
        "34_discourse_constellation",
        "30_topic_lens_divergence",
        "33_two_tag_lens_comparison",
        "35_two_tag_lens_fingerprints",
        "08_tag_momentum",
        "36_lens_drift_dumbbell",
        "26_lens_drift",
        "32_reduced_daily_lens_scores",
    ]
    lines = [
        "# NewsLens Narrative Poster Materials",
        "",
        "## Core Claim",
        "",
        "NewsLens treats computational classification as navigational infrastructure for interpretive inquiry rather than automated truth assessment.",
        "",
        "## Research Context / Methodological Intervention",
        "",
        "NewsLens operates at the intersection of computational media analysis, discourse studies, and digital humanities. It organizes computational annotations into navigable interpretive surfaces that support comparative reading across media discourse.",
        "",
        "## Comparative Discourse Reading",
        "",
        "Use the article-level and event-level plurality panels as the visual center of the poster. These figures show how the same discourse object can become readable through several rubric-mediated views without reducing interpretation to a single conclusion.",
        "",
        "## Computational Annotation and Close Reading",
        "",
        "The system does not automate meaning. It provides inspectable computational mediation: articles, lenses, rubric concepts, source context, tags, and temporal movement remain available as scaffolds for close reading.",
        "",
        "## Lens-Mediated Discourse Patterns",
        "",
        "Use the tag constellation and divergence heatmap to show how rhetorical organization emerges across lenses. Treat formation labels as interpretive summaries of annotation patterns, not fixed taxonomies.",
        "",
        "## Temporal Attention Movement",
        "",
        "Use tag momentum, lens drift, and reduced daily lens movement to show how computational annotations can help navigate changing discourse over time.",
        "",
        "## Methodological Contribution",
        "",
        "The contribution is analytical pluralism: computational annotation becomes a navigational interface for comparative discourse inquiry while keeping interpretive ambiguity visible and inspectable.",
        "",
        "## Suggested Figure Order",
        "",
    ]
    for figure_id in order:
        figure = figure_lookup.get(figure_id)
        if not figure:
            continue
        lines.extend(
            [
                f"### {figure['title']}",
                "",
                f"- File: `{figure['svg']}`",
                f"- Figure label: {figure['caption']}",
                f"- Method: {figure.get('method', '')}",
                f"- Encoding: {figure.get('encoding', '')}",
                f"- Interpretive note: {figure.get('interpretive_note', '')}",
                "",
            ]
        )
    return "\n".join(lines) + "\n"


def write_poster_sections(output_dir: Path, manifest: dict[str, Any]) -> None:
    output_dir.joinpath("poster_sections.md").write_text(narrative_poster_sections(manifest), encoding="utf-8")


def export_poster_figures(
    *,
    payload: dict[str, Any],
    output_dir: Path = DEFAULT_OUTPUT_DIR,
    source_label: str = DEFAULT_STATS_URL,
    figure_specs: tuple[FigureSpec, ...] = POSTER_FIGURES,
    source_filter: tuple[str, ...] = (),
    write_sections: bool = False,
    tag_cluster_label_overrides: dict[str, str] | None = None,
) -> dict[str, Any]:
    derived = filter_derived_for_sources(stats_derived(payload), source_filter)
    previous_label_overrides = dict(TAG_CLUSTER_LABEL_OVERRIDES)
    if tag_cluster_label_overrides is not None:
        set_tag_cluster_label_overrides(tag_cluster_label_overrides)
    output_dir.mkdir(parents=True, exist_ok=True)
    svg_dir = output_dir / "svg"
    pdf_dir = output_dir / "pdf"
    svg_dir.mkdir(parents=True, exist_ok=True)
    pdf_dir.mkdir(parents=True, exist_ok=True)

    manifest: dict[str, Any] = {
        "generated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "source": source_label,
        "stats_status": payload.get("status"),
        "stats_generated_at": _as_dict(payload.get("meta")).get("generated_at"),
        "source_filter": list(source_filter),
        "figures": [],
    }
    try:
        pdf_paths: list[Path] = []
        for spec in figure_specs:
            built = build_figure(derived, spec)
            notes = figure_method_notes(spec)
            svg_path = svg_dir / f"{spec.id}.svg"
            pdf_path = pdf_dir / f"{spec.id}.pdf"
            built.figure.write_image(str(svg_path), format="svg", width=spec.width, height=spec.height)
            built.figure.write_image(str(pdf_path), format="pdf", width=spec.width, height=spec.height)
            pdf_paths.append(pdf_path)
            manifest["figures"].append(
                {
                    "id": spec.id,
                    "title": spec.title,
                    "caption": built.caption,
                    "method": notes["method"],
                    "encoding": notes["encoding"],
                    "interpretive_note": notes["interpretive_note"],
                    "status": built.status,
                    "reason": built.reason,
                    "required_keys": list(spec.required_keys),
                    "builder": spec.builder,
                    "width": spec.width,
                    "height": spec.height,
                    "svg": str(svg_path.relative_to(output_dir)),
                    "pdf": str(pdf_path.relative_to(output_dir)),
                }
            )
    finally:
        if tag_cluster_label_overrides is not None:
            set_tag_cluster_label_overrides(previous_label_overrides)

    merge_pdfs(pdf_paths, output_dir / "poster_figures.pdf")
    manifest_path = output_dir / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    write_readme(output_dir, manifest)
    if write_sections:
        write_poster_sections(output_dir, manifest)
    return manifest


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Export poster-ready NewsLens figures as SVG and PDF.")
    parser.add_argument("--stats-url", default=DEFAULT_STATS_URL, help="Stats API URL to read when --stats-json is not provided.")
    parser.add_argument("--stats-json", type=Path, default=None, help="Local stats JSON file to read instead of the API.")
    parser.add_argument("--output-dir", type=Path, default=None, help="Directory for SVG/PDF exports.")
    parser.add_argument("--preset", choices=sorted(FIGURE_PRESETS), default="poster", help="Named figure preset to export.")
    parser.add_argument("--sources", default="", help="Comma-separated source filter, for example 'Al Jazeera,NPR,Fox News'.")
    parser.add_argument("--tag-cluster-labels-json", type=Path, default=None, help="Optional GPT-generated tag cluster label JSON to apply during export.")
    parser.add_argument("--write-tag-cluster-labels", type=Path, default=None, help="Generate GPT tag cluster labels to this JSON file before exporting.")
    parser.add_argument("--tag-cluster-label-model", default=DEFAULT_TAG_CLUSTER_LABEL_MODEL, help="OpenAI model for --write-tag-cluster-labels.")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    source_label = str(args.stats_json) if args.stats_json else str(args.stats_url)
    figure_specs = FIGURE_PRESETS[args.preset]
    source_filter = parse_source_filter(args.sources)
    if args.preset == "source-trio-matrix" and not source_filter:
        source_filter = SOURCE_TRIO
    output_dir = args.output_dir or (
        Path("data/exports/source_trio_matrix")
        if args.preset == "source-trio-matrix"
        else Path("data/exports/newslens_narrative_poster_materials")
        if args.preset == "poster-narrative"
        else DEFAULT_OUTPUT_DIR
    )
    payload = load_stats_payload(stats_url=args.stats_url, stats_json=args.stats_json)
    tag_cluster_label_overrides = load_tag_cluster_label_overrides(args.tag_cluster_labels_json)
    if args.write_tag_cluster_labels:
        derived_for_labels = filter_derived_for_sources(stats_derived(payload), source_filter)
        label_file = write_openai_tag_cluster_label_file(
            derived=derived_for_labels,
            output_path=args.write_tag_cluster_labels,
            model=args.tag_cluster_label_model,
        )
        tag_cluster_label_overrides = {
            str(_as_dict(row).get("fingerprint")): sanitize_tag_cluster_label(_as_dict(row).get("label"))
            for row in _as_list(_as_dict(label_file).get("labels"))
            if _as_dict(row).get("fingerprint") and sanitize_tag_cluster_label(_as_dict(row).get("label"))
        }
    manifest = export_poster_figures(
        payload=payload,
        output_dir=output_dir,
        source_label=source_label,
        figure_specs=figure_specs,
        source_filter=source_filter,
        write_sections=args.preset == "poster-narrative",
        tag_cluster_label_overrides=tag_cluster_label_overrides or None,
    )
    status_counts: dict[str, int] = defaultdict(int)
    for figure in manifest["figures"]:
        status_counts[str(figure["status"])] += 1
    print(
        json.dumps(
            {
                "status": "ok",
                "output_dir": str(output_dir),
                "preset": args.preset,
                "source_filter": list(source_filter),
                "tag_cluster_labels": str(args.write_tag_cluster_labels or args.tag_cluster_labels_json or ""),
                "figure_count": len(manifest["figures"]),
                "status_counts": dict(status_counts),
                "combined_pdf": str(output_dir / "poster_figures.pdf"),
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
