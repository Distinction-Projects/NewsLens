from __future__ import annotations

from collections import defaultdict

import dash
import dash_bootstrap_components as dbc
import plotly.graph_objects as go
from dash import Input, Output, State, callback, ctx, dcc, html

from src.pages.news_page_utils import api_get, build_news_intro, build_status_alert, snapshot_param


dash.register_page(
    __name__,
    path="/news/lens-explorer",
    name="News Lens Explorer",
    title="NewsLens | News Lens Explorer",
)


def _empty_figure(title: str) -> go.Figure:
    figure = go.Figure()
    figure.update_layout(title=title, template="plotly_white", margin={"l": 30, "r": 20, "t": 60, "b": 40})
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
    for lens_name, details in lens_scores.items():
        if not isinstance(lens_name, str) or not isinstance(details, dict):
            continue
        percent = details.get("percent")
        if isinstance(percent, (int, float)):
            normalized_scores[lens_name] = float(percent)
            continue

        value = details.get("value")
        max_value = details.get("max_value")
        if isinstance(value, (int, float)) and isinstance(max_value, (int, float)) and max_value > 0:
            normalized_scores[lens_name] = (float(value) / float(max_value)) * 100.0
    return normalized_scores


def _article_rows(articles: list[dict], lens_maxima: dict[str, float]) -> tuple[list[dict], str]:
    _ = lens_maxima
    rows: list[dict] = []
    for article in articles:
        normalized_scores = _full_score_lens_scores(article)
        if not normalized_scores:
            continue

        strongest_lens, strongest_percent = max(normalized_scores.items(), key=lambda item: item[1])
        source = article.get("source") if isinstance(article.get("source"), dict) else {}
        score = article.get("score") if isinstance(article.get("score"), dict) else {}
        rows.append(
            {
                "title": article.get("title", "Untitled"),
                "source": source.get("name", "Unknown"),
                "published": article.get("published"),
                "lens_scores": normalized_scores,
                "strongest_lens": strongest_lens,
                "strongest_percent": strongest_percent,
            }
        )
    if not rows:
        return rows, "no lens data"
    return rows, "all scored articles"


def _lens_options(lens_names: list[str]) -> list[dict]:
    return [{"label": lens_name, "value": lens_name} for lens_name in lens_names]


def _selected_gap_details(row: dict, selected_lens: str) -> tuple[float | None, str, float | None]:
    selected_value = row["lens_scores"].get(selected_lens)
    if not isinstance(selected_value, (int, float)):
        return None, "n/a", None

    runner_up_name = "n/a"
    runner_up_value = None
    for lens_name, lens_value in row["lens_scores"].items():
        if lens_name == selected_lens or not isinstance(lens_value, (int, float)):
            continue
        if not isinstance(runner_up_value, (int, float)) or lens_value > runner_up_value:
            runner_up_name = lens_name
            runner_up_value = float(lens_value)
    baseline = float(runner_up_value) if isinstance(runner_up_value, (int, float)) else 0.0
    return float(selected_value) - baseline, runner_up_name, runner_up_value


def _dominant_lens_distribution_figure(
    article_rows: list[dict],
    lens_names: list[str],
    lens_average_rows: list[dict] | None = None,
) -> go.Figure:
    _ = lens_average_rows
    if not article_rows or not lens_names:
        return _empty_figure("Strongest Lens Distribution Across Articles")

    dominant_counts: defaultdict[str, int] = defaultdict(int)
    for row in article_rows:
        dominant_counts[str(row.get("strongest_lens") or "n/a")] += 1
    counts = [dominant_counts.get(lens_name, 0) for lens_name in lens_names]

    figure = go.Figure(data=[go.Bar(x=lens_names, y=counts, marker_color="#6f42c1")])
    figure.update_layout(
        title="Strongest Lens Distribution Across Articles",
        template="plotly_white",
        yaxis_title="Article Count",
    )
    return figure


def _selected_lens_figure(article_rows: list[dict], selected_lens: str | None, top_n: int) -> go.Figure:
    if not article_rows or not selected_lens:
        return _empty_figure("Selected Lens Separation by Article")

    rows = []
    for row in article_rows:
        gap, runner_up_lens, runner_up_percent = _selected_gap_details(row, selected_lens)
        selected_percent = row["lens_scores"].get(selected_lens)
        if not isinstance(gap, (int, float)) or not isinstance(selected_percent, (int, float)):
            continue
        rows.append(
            {
                **row,
                "selected_percent": float(selected_percent),
                "runner_up_lens": runner_up_lens,
                "runner_up_percent": runner_up_percent,
                "gap_percent": float(gap),
            }
        )

    rows = sorted(rows, key=lambda row: (row["gap_percent"], row["selected_percent"]), reverse=True)[:top_n]
    if not rows:
        return _empty_figure("Selected Lens Separation by Article")

    figure = go.Figure(
        data=[
            go.Bar(
                x=[row["gap_percent"] for row in rows],
                y=[_truncate_title(row["title"]) for row in rows],
                orientation="h",
                marker_color=["#198754" if row["gap_percent"] >= 0 else "#dc3545" for row in rows],
                customdata=[
                    [
                        row["source"],
                        row["selected_percent"],
                        row["runner_up_lens"],
                        (
                            f"{float(row['runner_up_percent']):.1f}"
                            if isinstance(row.get("runner_up_percent"), (int, float))
                            else "n/a"
                        ),
                    ]
                    for row in rows
                ],
                hovertemplate=(
                    "%{y}<br>"
                    "Source: %{customdata[0]}<br>"
                    f"{selected_lens} %: "
                    "%{customdata[1]:.1f}<br>"
                    "Runner-up Lens: %{customdata[2]}<br>"
                    "Runner-up %: %{customdata[3]}<br>"
                    "Gap vs Runner-up: %{x:.1f}<extra></extra>"
                ),
            )
        ]
    )
    figure.update_layout(
        title=f"{selected_lens} Separation vs Runner-up Lens",
        template="plotly_white",
        yaxis={"autorange": "reversed"},
        xaxis_title="Gap % (Selected Lens - Runner-up Lens)",
    )
    return figure


def _summary_cards(article_rows: list[dict], selected_lens: str | None, lens_summary: dict | None = None) -> list:
    summary = lens_summary if isinstance(lens_summary, dict) else {}
    article_count = int(summary.get("article_count")) if isinstance(summary.get("article_count"), (int, float)) else len(article_rows)

    selected_values = [
        float(row["lens_scores"].get(selected_lens))
        for row in article_rows
        if selected_lens and isinstance(row["lens_scores"].get(selected_lens), (int, float))
    ]
    selected_count = len(selected_values)
    selected_mean = (sum(selected_values) / selected_count) if selected_values else None
    selected_spread = (
        ((sum((value - selected_mean) ** 2 for value in selected_values) / selected_count) ** 0.5)
        if selected_values and isinstance(selected_mean, (int, float))
        else None
    )

    gap_values = []
    selected_dominant = 0
    for row in article_rows:
        if not selected_lens:
            continue
        gap, _, _ = _selected_gap_details(row, selected_lens)
        if isinstance(gap, (int, float)):
            gap_values.append(float(gap))
            if row.get("strongest_lens") == selected_lens:
                selected_dominant += 1
    average_gap = (sum(gap_values) / len(gap_values)) if gap_values else None
    dominance_share = ((selected_dominant / len(gap_values)) * 100.0) if gap_values else None

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
        ("Articles with Lens Scores", article_count),
        (
            f"{selected_lens} Coverage" if selected_lens else "Selected Lens Coverage",
            f"{selected_count}/{article_count}" if article_count > 0 else "0/0",
        ),
        (
            f"{selected_lens} Dominance Share" if selected_lens else "Selected Lens Dominance Share",
            f"{float(dominance_share):.1f}%"
            if isinstance(dominance_share, (int, float))
            else "n/a",
        ),
        (
            f"{selected_lens} Spread (std dev)" if selected_lens else "Selected Lens Spread (std dev)",
            f"{float(selected_spread):.1f}" if isinstance(selected_spread, (int, float)) else "n/a",
        ),
        (
            f"{selected_lens} Avg Gap vs Runner-up" if selected_lens else "Selected Lens Avg Gap vs Runner-up",
            f"{float(average_gap):.1f}" if isinstance(average_gap, (int, float)) else "n/a",
        ),
        ("Most Common Strongest Lens", dominant_lens),
    ]
    return [
        dbc.Col(
            dbc.Card(
                dbc.CardBody([html.P(label, className="text-muted mb-1"), html.H4(str(value), className="mb-0")]),
                className="shadow-sm",
            ),
            md=6,
            lg=2,
            className="mb-3",
        )
        for label, value in cards
    ]


def _article_table(article_rows: list[dict], selected_lens: str | None, top_n: int):
    if not article_rows or not selected_lens:
        return dbc.Alert("No article lens breakdown is available.", color="warning", className="mb-0")

    rows = []
    for row in article_rows:
        gap, runner_up_lens, runner_up_percent = _selected_gap_details(row, selected_lens)
        selected_percent = row["lens_scores"].get(selected_lens)
        if not isinstance(gap, (int, float)) or not isinstance(selected_percent, (int, float)):
            continue
        rows.append(
            {
                **row,
                "selected_percent": float(selected_percent),
                "runner_up_lens": runner_up_lens,
                "runner_up_percent": runner_up_percent,
                "gap_percent": float(gap),
            }
        )
    rows = sorted(rows, key=lambda row: (row["gap_percent"], row["selected_percent"]), reverse=True)[:top_n]
    if not rows:
        return dbc.Alert("No rows are available for the selected lens.", color="warning", className="mb-0")

    header = html.Thead(
        html.Tr(
            [
                html.Th("Title"),
                html.Th("Source"),
                html.Th(f"{selected_lens} %"),
                html.Th("Runner-up Lens"),
                html.Th("Runner-up %"),
                html.Th("Gap vs Runner-up"),
                html.Th("Strongest Lens"),
                html.Th("Strongest %"),
            ]
        )
    )
    body_rows = []
    for row in rows:
        body_rows.append(
            html.Tr(
                [
                    html.Td(row["title"]),
                    html.Td(row["source"]),
                    html.Td(f"{float(row['selected_percent']):.1f}"),
                    html.Td(row["runner_up_lens"]),
                    html.Td(
                        f"{float(row['runner_up_percent']):.1f}"
                        if isinstance(row.get("runner_up_percent"), (int, float))
                        else "n/a"
                    ),
                    html.Td(f"{float(row['gap_percent']):.1f}"),
                    html.Td(row["strongest_lens"]),
                    html.Td(f"{float(row['strongest_percent']):.1f}" if isinstance(row.get("strongest_percent"), (int, float)) else "n/a"),
                ]
            )
        )
    return dbc.Table([header, html.Tbody(body_rows)], bordered=True, striped=True, hover=True, responsive=True, size="sm")


layout = dbc.Container(
    [
        dcc.Interval(id="news-lens-explorer-load", interval=50, n_intervals=0, max_intervals=1),
        dbc.Row([dbc.Col(html.H3("News Lens Explorer", className="mb-2"), width=12)]),
        build_news_intro(
            "Explore article-level lens values and distributions interactively."
        ),
        dbc.Row(
            [
                dbc.Col(
                    [
                        dbc.Label("Data mode"),
                        dcc.Dropdown(
                            id="news-lens-explorer-mode",
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
                            id="news-lens-explorer-snapshot-date",
                            type="date",
                            className="form-control",
                            disabled=True,
                        ),
                    ],
                    md=2,
                ),
                dbc.Col(
                    [
                        dbc.Label("Lens"),
                        dcc.Dropdown(id="news-lens-explorer-lens", options=[], value=None, clearable=False),
                    ],
                    md=3,
                ),
                dbc.Col(
                    [
                        dbc.Label("Top N articles"),
                        dcc.Input(
                            id="news-lens-explorer-top-n",
                            type="number",
                            min=3,
                            max=50,
                            step=1,
                            value=10,
                            className="form-control",
                        ),
                    ],
                    md=2,
                ),
                dbc.Col(
                    [
                        dbc.Label("Actions"),
                        dbc.Button("Refresh", id="news-lens-explorer-refresh", color="secondary"),
                    ],
                    md=1,
                ),
                dbc.Col(html.Div(id="news-lens-explorer-status"), md=2),
            ],
            className="mb-3",
        ),
        dbc.Row(id="news-lens-explorer-cards"),
        dbc.Row(
            [
                dbc.Col(dcc.Graph(id="news-lens-explorer-selected-graph"), lg=7, className="mb-3"),
                dbc.Col(dcc.Graph(id="news-lens-explorer-average-graph"), lg=5, className="mb-3"),
            ]
        ),
        dbc.Row([dbc.Col(html.Div(id="news-lens-explorer-table"), width=12)]),
    ],
    fluid=True,
    className="py-4",
)


@callback(
    Output("news-lens-explorer-status", "children"),
    Output("news-lens-explorer-lens", "options"),
    Output("news-lens-explorer-lens", "value"),
    Output("news-lens-explorer-cards", "children"),
    Output("news-lens-explorer-selected-graph", "figure"),
    Output("news-lens-explorer-average-graph", "figure"),
    Output("news-lens-explorer-table", "children"),
    Input("news-lens-explorer-load", "n_intervals"),
    Input("news-lens-explorer-refresh", "n_clicks"),
    Input("news-lens-explorer-lens", "value"),
    State("news-lens-explorer-mode", "value"),
    State("news-lens-explorer-snapshot-date", "value"),
    State("news-lens-explorer-top-n", "value"),
)
def load_news_lens_explorer(_load_tick, _refresh_clicks, selected_lens, data_mode, snapshot_date, top_n):
    force_refresh = ctx.triggered_id == "news-lens-explorer-refresh"
    common_params = {
        "snapshot_date": snapshot_param(data_mode, snapshot_date),
        "refresh": "true" if force_refresh else None,
    }
    stats_code, stats_payload = api_get("/api/news/stats", common_params)
    n_value = int(top_n) if isinstance(top_n, (int, float)) and top_n else 10
    n_value = max(3, min(50, n_value))

    if stats_code != 200:
        stats_error = stats_payload.get("error", "Unknown error")
        empty = _empty_figure("No data")
        alert = dbc.Alert(
            f"Lens data error: stats={stats_code} ({stats_error})",
            color="danger",
        )
        return alert, [], None, _summary_cards([], None), empty, empty, dbc.Alert("No table data.", color="warning")

    meta = stats_payload.get("meta", {})
    derived = stats_payload.get("data", {}).get("derived", {})
    lens_views = derived.get("lens_views", {}) if isinstance(derived, dict) else {}
    article_rows = lens_views.get("article_rows", []) if isinstance(lens_views.get("article_rows"), list) else []
    coverage_mode = str(lens_views.get("coverage_mode") or "no lens data")
    lens_summary = lens_views.get("summary", {}) if isinstance(lens_views.get("summary"), dict) else {}
    lens_average_rows = lens_summary.get("lens_average_rows", []) if isinstance(lens_summary.get("lens_average_rows"), list) else []
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
        _summary_cards(article_rows, effective_lens, lens_summary),
        _selected_lens_figure(article_rows, effective_lens, n_value),
        _dominant_lens_distribution_figure(article_rows, lens_names, lens_average_rows),
        _article_table(article_rows, effective_lens, n_value),
    )


@callback(
    Output("news-lens-explorer-snapshot-date", "disabled"),
    Input("news-lens-explorer-mode", "value"),
)
def toggle_lens_explorer_snapshot_input(data_mode):
    return data_mode != "snapshot"
