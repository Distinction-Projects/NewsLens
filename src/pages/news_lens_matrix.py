from __future__ import annotations

from collections import defaultdict

import dash
import dash_bootstrap_components as dbc
import plotly.graph_objects as go
from dash import Input, Output, State, callback, ctx, dcc, html

from src.pages.news_page_utils import api_get, build_status_alert, snapshot_param


dash.register_page(
    __name__,
    path="/news/lens-matrix",
    name="News Lens Matrix",
    title="NewsLens | News Lens Matrix",
)


def _empty_figure(title: str) -> go.Figure:
    figure = go.Figure()
    figure.update_layout(
        title=title,
        template="plotly_white",
        margin={"l": 30, "r": 20, "t": 60, "b": 40},
    )
    return figure


def _truncate_title(title: object, limit: int = 72) -> str:
    text = str(title or "Untitled")
    if len(text) <= limit:
        return text
    return f"{text[: limit - 3]}..."


def _lens_max_map(lens_summary: dict) -> dict[str, float]:
    lenses = lens_summary.get("lenses", []) if isinstance(lens_summary, dict) else []
    result: dict[str, float] = {}
    for row in lenses:
        name = row.get("name")
        max_total = row.get("max_total")
        if isinstance(name, str) and isinstance(max_total, (int, float)) and max_total > 0:
            result[name] = float(max_total)
    return result


def _full_score_lens_scores(article: dict) -> dict[str, float]:
    score = article.get("score")
    if not isinstance(score, dict):
        return {}

    lens_scores = score.get("lens_scores")
    if not isinstance(lens_scores, dict):
        return {}

    normalized_scores: dict[str, float] = {}
    for lens_name, payload in lens_scores.items():
        if not isinstance(lens_name, str) or not isinstance(payload, dict):
            continue
        percent = payload.get("percent")
        if isinstance(percent, (int, float)):
            normalized_scores[lens_name] = float(percent)
            continue

        value = payload.get("value")
        max_value = payload.get("max_value")
        if isinstance(value, (int, float)) and isinstance(max_value, (int, float)) and max_value > 0:
            normalized_scores[lens_name] = (float(value) / float(max_value)) * 100.0
    return normalized_scores


def _legacy_high_score_lens_scores(article: dict, lens_maxima: dict[str, float]) -> dict[str, float]:
    high_score = article.get("high_score")
    if not isinstance(high_score, dict):
        return {}

    lens_scores = high_score.get("lens_scores")
    if not isinstance(lens_scores, dict):
        return {}

    normalized_scores: dict[str, float] = {}
    for lens_name, value in lens_scores.items():
        if not isinstance(lens_name, str) or not isinstance(value, (int, float)):
            continue
        max_total = lens_maxima.get(lens_name)
        if isinstance(max_total, (int, float)) and max_total > 0:
            normalized_scores[lens_name] = (float(value) / float(max_total)) * 100.0
        else:
            normalized_scores[lens_name] = float(value)
    return normalized_scores


def _matrix_rows(articles: list[dict], lens_maxima: dict[str, float]) -> tuple[list[dict], str]:
    rows: list[dict] = []
    data_modes: set[str] = set()
    for article in articles:
        lens_scores = _full_score_lens_scores(article)
        row_mode = "full"
        if not lens_scores:
            lens_scores = _legacy_high_score_lens_scores(article, lens_maxima)
            row_mode = "legacy"

        if not lens_scores:
            continue

        data_modes.add(row_mode)
        score = article.get("score") if isinstance(article.get("score"), dict) else {}
        high_score = article.get("high_score") if isinstance(article.get("high_score"), dict) else {}
        source = article.get("source") if isinstance(article.get("source"), dict) else {}
        strongest_lens, strongest_percent = max(lens_scores.items(), key=lambda item: item[1])
        rows.append(
            {
                "id": article.get("id"),
                "title": article.get("title", "Untitled"),
                "source": source.get("name", "Unknown"),
                "published": article.get("published"),
                "overall_percent": score.get("percent")
                if isinstance(score.get("percent"), (int, float))
                else high_score.get("overall_percent"),
                "lens_scores": lens_scores,
                "strongest_lens": strongest_lens,
                "strongest_percent": strongest_percent,
            }
        )

    if not rows:
        return rows, "no lens data"
    if data_modes == {"full"}:
        return rows, "all scored articles"
    if data_modes == {"legacy"}:
        return rows, "high-score fallback"
    return rows, "mixed"


def _lens_options(lens_names: list[str]) -> list[dict]:
    return [{"label": lens_name, "value": lens_name} for lens_name in lens_names]


def _sorted_rows(article_rows: list[dict], selected_lens: str | None) -> list[dict]:
    if not selected_lens:
        return sorted(
            article_rows,
            key=lambda row: (
                float(row.get("overall_percent") or 0.0),
                float(row.get("strongest_percent") or 0.0),
            ),
            reverse=True,
        )

    return sorted(
        article_rows,
        key=lambda row: (
            float(row["lens_scores"].get(selected_lens) or 0.0),
            float(row.get("overall_percent") or 0.0),
            float(row.get("strongest_percent") or 0.0),
        ),
        reverse=True,
    )


def _coverage_cards(article_rows: list[dict], selected_lens: str | None, lens_summary: dict | None = None) -> list:
    summary = lens_summary if isinstance(lens_summary, dict) else {}
    article_count = int(summary.get("article_count")) if isinstance(summary.get("article_count"), (int, float)) else len(article_rows)

    overall_avg = summary.get("overall_avg")
    if not isinstance(overall_avg, (int, float)):
        overall_values = [
            float(row["overall_percent"])
            for row in article_rows
            if isinstance(row.get("overall_percent"), (int, float))
        ]
        overall_avg = (sum(overall_values) / len(overall_values)) if overall_values else None

    selected_avg = None
    lens_average_rows = summary.get("lens_average_rows")
    if selected_lens and isinstance(lens_average_rows, list):
        for row in lens_average_rows:
            if not isinstance(row, dict):
                continue
            if row.get("lens") == selected_lens and isinstance(row.get("mean"), (int, float)):
                selected_avg = float(row["mean"])
                break
    if selected_avg is None:
        selected_values = [
            float(row["lens_scores"][selected_lens])
            for row in article_rows
            if selected_lens and isinstance(row["lens_scores"].get(selected_lens), (int, float))
        ]
        selected_avg = (sum(selected_values) / len(selected_values)) if selected_values else None

    dominant_lens = "n/a"
    dominant_counts = summary.get("dominant_lens_counts")
    if isinstance(dominant_counts, list) and dominant_counts:
        first = dominant_counts[0]
        if isinstance(first, dict) and isinstance(first.get("lens"), str) and first.get("lens"):
            dominant_lens = first["lens"]
    if dominant_lens == "n/a":
        fallback_counts: defaultdict[str, int] = defaultdict(int)
        for row in article_rows:
            fallback_counts[row["strongest_lens"]] += 1
        dominant_lens = max(fallback_counts.items(), key=lambda item: item[1])[0] if fallback_counts else "n/a"

    cards = [
        ("Articles in Matrix", article_count),
        (
            f"Avg {selected_lens} %" if selected_lens else "Avg Selected Lens %",
            f"{float(selected_avg):.1f}" if isinstance(selected_avg, (int, float)) else "n/a",
        ),
        ("Avg Overall %", f"{float(overall_avg):.1f}" if isinstance(overall_avg, (int, float)) else "n/a"),
        ("Most Common Strongest Lens", dominant_lens),
    ]
    return [
        dbc.Col(
            dbc.Card(
                dbc.CardBody(
                    [html.P(label, className="text-muted mb-1"), html.H4(str(value), className="mb-0")]
                ),
                className="shadow-sm",
            ),
            md=6,
            lg=3,
            className="mb-3",
        )
        for label, value in cards
    ]


def _heatmap_figure(article_rows: list[dict], lens_names: list[str], selected_lens: str | None, top_n: int) -> go.Figure:
    if not article_rows or not lens_names:
        return _empty_figure("Lens Percent Matrix")

    rows = _sorted_rows(article_rows, selected_lens)[:top_n]
    if not rows:
        return _empty_figure("Lens Percent Matrix")

    z_values = []
    for row in rows:
        z_values.append([float(row["lens_scores"].get(lens_name) or 0.0) for lens_name in lens_names])

    figure = go.Figure(
        data=[
            go.Heatmap(
                z=z_values,
                x=lens_names,
                y=[_truncate_title(row["title"], limit=56) for row in rows],
                zmin=0,
                zmax=100,
                colorscale="YlOrRd",
                colorbar={"title": "Lens %"},
                customdata=[
                    [
                        [row["source"], row.get("overall_percent"), row["strongest_lens"]]
                        for _ in lens_names
                    ]
                    for row in rows
                ],
                hovertemplate=(
                    "Article: %{y}<br>"
                    "Lens: %{x}<br>"
                    "Lens %: %{z:.1f}<br>"
                    "Source: %{customdata[0]}<br>"
                    "Overall %: %{customdata[1]:.1f}<br>"
                    "Strongest Lens: %{customdata[2]}<extra></extra>"
                ),
            )
        ]
    )
    figure.update_layout(
        title="Lens Percent Matrix",
        template="plotly_white",
        xaxis_title="Lens",
        yaxis_title="Article",
    )
    return figure


def _selected_lens_scatter(article_rows: list[dict], selected_lens: str | None, top_n: int) -> go.Figure:
    if not article_rows or not selected_lens:
        return _empty_figure("Selected Lens vs Overall Score")

    rows = [
        row
        for row in _sorted_rows(article_rows, selected_lens)[:top_n]
        if isinstance(row["lens_scores"].get(selected_lens), (int, float))
        and isinstance(row.get("overall_percent"), (int, float))
    ]
    if not rows:
        return _empty_figure("Selected Lens vs Overall Score")

    figure = go.Figure(
        data=[
            go.Scatter(
                x=[row["lens_scores"][selected_lens] for row in rows],
                y=[row["overall_percent"] for row in rows],
                mode="markers+text",
                marker={"size": 12, "color": "#0d6efd"},
                text=[_truncate_title(row["title"], limit=28) for row in rows],
                textposition="top center",
                customdata=[[row["source"], row["strongest_lens"]] for row in rows],
                hovertemplate=(
                    "%{text}<br>"
                    f"{selected_lens} %: "
                    "%{x:.1f}<br>"
                    "Overall %: %{y:.1f}<br>"
                    "Source: %{customdata[0]}<br>"
                    "Strongest Lens: %{customdata[1]}<extra></extra>"
                ),
            )
        ]
    )
    figure.update_layout(
        title=f"{selected_lens} vs Overall Score",
        template="plotly_white",
        xaxis_title=f"{selected_lens} %",
        yaxis_title="Overall %",
        yaxis={"range": [0, 100]},
        xaxis={"range": [0, 100]},
    )
    return figure


def _matrix_table(article_rows: list[dict], lens_names: list[str], selected_lens: str | None, top_n: int):
    if not article_rows or not lens_names:
        return dbc.Alert("No lens matrix data is available.", color="warning", className="mb-0")

    rows = _sorted_rows(article_rows, selected_lens)[:top_n]
    visible_lenses = lens_names[:4]
    header = html.Thead(
        html.Tr(
            [
                html.Th("Title"),
                html.Th("Source"),
                html.Th("Overall %"),
                html.Th("Strongest Lens"),
            ]
            + [html.Th(f"{lens_name} %") for lens_name in visible_lenses]
        )
    )
    body_rows = []
    for row in rows:
        body_rows.append(
            html.Tr(
                [
                    html.Td(row["title"]),
                    html.Td(row["source"]),
                    html.Td(
                        f"{float(row['overall_percent']):.1f}"
                        if isinstance(row.get("overall_percent"), (int, float))
                        else "n/a"
                    ),
                    html.Td(row["strongest_lens"]),
                ]
                + [
                    html.Td(
                        f"{float(row['lens_scores'].get(lens_name)):.1f}"
                        if isinstance(row["lens_scores"].get(lens_name), (int, float))
                        else "n/a"
                    )
                    for lens_name in visible_lenses
                ]
            )
        )
    return dbc.Table(
        [header, html.Tbody(body_rows)],
        bordered=True,
        striped=True,
        hover=True,
        responsive=True,
        size="sm",
    )


layout = dbc.Container(
    [
        dcc.Interval(id="news-lens-matrix-load", interval=50, n_intervals=0, max_intervals=1),
        dbc.Row([dbc.Col(html.H3("News Lens Matrix", className="mb-2"), width=12)]),
        dbc.Row(
            [
                dbc.Col(
                    html.P(
                        "This page brings the lens-matrix notebook view into NewsLens. It ranks articles by a selected "
                        "lens, shows the lens-by-article heatmap, and falls back to the legacy high-score subset when "
                        "the full contract is not available.",
                        className="text-muted",
                    ),
                    width=12,
                )
            ]
        ),
        dbc.Row(
            [
                dbc.Col(
                    [
                        dbc.Label("Data mode"),
                        dcc.Dropdown(
                            id="news-lens-matrix-mode",
                            options=[
                                {"label": "Current", "value": "current"},
                                {"label": "Snapshot", "value": "snapshot"},
                            ],
                            value="current",
                            clearable=False,
                        ),
                    ],
                    md=2,
                ),
                dbc.Col(
                    [
                        dbc.Label("Snapshot date (UTC)"),
                        dcc.Input(
                            id="news-lens-matrix-snapshot-date",
                            type="date",
                            className="form-control",
                            disabled=True,
                        ),
                    ],
                    md=2,
                ),
                dbc.Col(
                    [
                        dbc.Label("Sort lens"),
                        dcc.Dropdown(id="news-lens-matrix-lens", options=[], value=None, clearable=False),
                    ],
                    md=3,
                ),
                dbc.Col(
                    [
                        dbc.Label("Top N articles"),
                        dcc.Input(
                            id="news-lens-matrix-top-n",
                            type="number",
                            min=5,
                            max=40,
                            step=1,
                            value=12,
                            className="form-control",
                        ),
                    ],
                    md=2,
                ),
                dbc.Col(
                    [
                        dbc.Label("Actions"),
                        dbc.Button("Refresh", id="news-lens-matrix-refresh", color="secondary"),
                    ],
                    md=1,
                ),
                dbc.Col(html.Div(id="news-lens-matrix-status"), md=2),
            ],
            className="mb-3",
        ),
        dbc.Row(id="news-lens-matrix-cards"),
        dbc.Row(
            [
                dbc.Col(dcc.Graph(id="news-lens-matrix-heatmap"), lg=8, className="mb-3"),
                dbc.Col(dcc.Graph(id="news-lens-matrix-scatter"), lg=4, className="mb-3"),
            ]
        ),
        dbc.Row([dbc.Col(html.Div(id="news-lens-matrix-table"), width=12)]),
    ],
    fluid=True,
    className="py-4",
)


@callback(
    Output("news-lens-matrix-status", "children"),
    Output("news-lens-matrix-lens", "options"),
    Output("news-lens-matrix-lens", "value"),
    Output("news-lens-matrix-cards", "children"),
    Output("news-lens-matrix-heatmap", "figure"),
    Output("news-lens-matrix-scatter", "figure"),
    Output("news-lens-matrix-table", "children"),
    Input("news-lens-matrix-load", "n_intervals"),
    Input("news-lens-matrix-refresh", "n_clicks"),
    Input("news-lens-matrix-lens", "value"),
    State("news-lens-matrix-mode", "value"),
    State("news-lens-matrix-snapshot-date", "value"),
    State("news-lens-matrix-top-n", "value"),
)
def load_news_lens_matrix(_load_tick, _refresh_clicks, selected_lens, data_mode, snapshot_date, top_n):
    force_refresh = ctx.triggered_id == "news-lens-matrix-refresh"
    common_params = {
        "snapshot_date": snapshot_param(data_mode, snapshot_date),
        "refresh": "true" if force_refresh else None,
    }
    stats_code, stats_payload = api_get("/api/news/stats", common_params)
    n_value = int(top_n) if isinstance(top_n, (int, float)) and top_n else 12
    n_value = max(5, min(40, n_value))

    if stats_code != 200:
        stats_error = stats_payload.get("error", "Unknown error")
        empty = _empty_figure("No data")
        alert = dbc.Alert(
            f"Lens matrix data error: stats={stats_code} ({stats_error})",
            color="danger",
        )
        return alert, [], None, _coverage_cards([], None), empty, empty, dbc.Alert(
            "No matrix table data.",
            color="warning",
        )

    meta = stats_payload.get("meta", {})
    derived = stats_payload.get("data", {}).get("derived", {})
    lens_views = derived.get("lens_views", {}) if isinstance(derived, dict) else {}
    article_rows = lens_views.get("article_rows", []) if isinstance(lens_views.get("article_rows"), list) else []
    coverage_mode = str(lens_views.get("coverage_mode") or "no lens data")
    lens_summary = lens_views.get("summary", {}) if isinstance(lens_views.get("summary"), dict) else {}
    article_count = int(lens_summary.get("article_count")) if isinstance(lens_summary.get("article_count"), (int, float)) else len(article_rows)
    lens_names = [str(name) for name in lens_views.get("lens_names", []) if isinstance(name, str) and name.strip()]
    if not lens_names:
        lens_names = sorted({lens_name for row in article_rows for lens_name in row["lens_scores"]})
    effective_lens = selected_lens if selected_lens in lens_names else (lens_names[0] if lens_names else None)

    return (
        build_status_alert(
            meta,
            leading_parts=[
                f"Articles with lens scores: {article_count}",
                f"Coverage: {coverage_mode}",
            ],
        ),
        _lens_options(lens_names),
        effective_lens,
        _coverage_cards(article_rows, effective_lens, lens_summary),
        _heatmap_figure(article_rows, lens_names, effective_lens, n_value),
        _selected_lens_scatter(article_rows, effective_lens, n_value),
        _matrix_table(article_rows, lens_names, effective_lens, n_value),
    )


@callback(
    Output("news-lens-matrix-snapshot-date", "disabled"),
    Input("news-lens-matrix-mode", "value"),
)
def toggle_lens_matrix_snapshot_input(data_mode):
    return data_mode != "snapshot"
