from __future__ import annotations

from collections import defaultdict

import dash
import dash_bootstrap_components as dbc
import plotly.graph_objects as go
from dash import Input, Output, State, callback, ctx, dcc, html

from src.pages.news_page_utils import api_get, build_status_alert, snapshot_param


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
                "overall_percent": score.get("percent") if isinstance(score.get("percent"), (int, float)) else None,
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


def _lens_average_figure(article_rows: list[dict], lens_names: list[str], lens_average_rows: list[dict] | None = None) -> go.Figure:
    if not article_rows or not lens_names:
        return _empty_figure("Average Lens Percent Across Available Articles")

    summary_rows = lens_average_rows if isinstance(lens_average_rows, list) else []
    summary_means = {
        str(row.get("lens")): float(row.get("mean"))
        for row in summary_rows
        if isinstance(row, dict) and isinstance(row.get("lens"), str) and isinstance(row.get("mean"), (int, float))
    }
    if summary_means:
        averages = [summary_means.get(lens_name, 0.0) for lens_name in lens_names]
    else:
        averages = []
        for lens_name in lens_names:
            values = [row["lens_scores"].get(lens_name) for row in article_rows if isinstance(row["lens_scores"].get(lens_name), (int, float))]
            averages.append(sum(values) / len(values) if values else 0.0)

    figure = go.Figure(data=[go.Bar(x=lens_names, y=averages, marker_color="#6f42c1")])
    figure.update_layout(title="Average Lens Percent Across Available Articles", template="plotly_white", yaxis={"range": [0, 100]})
    return figure


def _selected_lens_figure(article_rows: list[dict], selected_lens: str | None, top_n: int) -> go.Figure:
    if not article_rows or not selected_lens:
        return _empty_figure("Top Articles by Selected Lens")

    rows = sorted(
        (row for row in article_rows if isinstance(row["lens_scores"].get(selected_lens), (int, float))),
        key=lambda row: row["lens_scores"][selected_lens],
        reverse=True,
    )[:top_n]
    if not rows:
        return _empty_figure("Top Articles by Selected Lens")

    figure = go.Figure(
        data=[
            go.Bar(
                x=[row["lens_scores"][selected_lens] for row in rows],
                y=[_truncate_title(row["title"]) for row in rows],
                orientation="h",
                marker_color="#dc3545",
                customdata=[[row["source"], row.get("overall_percent")] for row in rows],
                hovertemplate="%{y}<br>Source: %{customdata[0]}<br>Lens %: %{x:.1f}<br>Overall %: %{customdata[1]:.1f}<extra></extra>",
            )
        ]
    )
    figure.update_layout(
        title=f"Top Articles by {selected_lens}",
        template="plotly_white",
        yaxis={"autorange": "reversed"},
        xaxis_title="Lens Percent",
    )
    return figure


def _summary_cards(article_rows: list[dict], selected_lens: str | None, lens_summary: dict | None = None) -> list:
    summary = lens_summary if isinstance(lens_summary, dict) else {}
    article_count = int(summary.get("article_count")) if isinstance(summary.get("article_count"), (int, float)) else len(article_rows)

    overall_avg = summary.get("overall_avg")
    if not isinstance(overall_avg, (int, float)):
        overall_values = [float(row["overall_percent"]) for row in article_rows if isinstance(row.get("overall_percent"), (int, float))]
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
        ("Articles with Lens Scores", article_count),
        ("Avg Overall %", f"{float(overall_avg):.1f}" if isinstance(overall_avg, (int, float)) else "n/a"),
        (
            f"Avg {selected_lens} %" if selected_lens else "Avg Selected Lens %",
            f"{float(selected_avg):.1f}" if isinstance(selected_avg, (int, float)) else "n/a",
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
            lg=3,
            className="mb-3",
        )
        for label, value in cards
    ]


def _article_table(article_rows: list[dict], selected_lens: str | None, top_n: int):
    if not article_rows or not selected_lens:
        return dbc.Alert("No article lens breakdown is available.", color="warning", className="mb-0")

    rows = sorted(
        (row for row in article_rows if isinstance(row["lens_scores"].get(selected_lens), (int, float))),
        key=lambda row: row["lens_scores"][selected_lens],
        reverse=True,
    )[:top_n]
    if not rows:
        return dbc.Alert("No rows are available for the selected lens.", color="warning", className="mb-0")

    header = html.Thead(
        html.Tr(
            [
                html.Th("Title"),
                html.Th("Source"),
                html.Th("Overall %"),
                html.Th(f"{selected_lens} %"),
                html.Th("Strongest Lens"),
                html.Th("Strongest %"),
            ]
        )
    )
    body_rows = []
    for row in rows:
        overall_percent = row.get("overall_percent")
        selected_percent = row["lens_scores"].get(selected_lens)
        body_rows.append(
            html.Tr(
                [
                    html.Td(row["title"]),
                    html.Td(row["source"]),
                    html.Td(f"{float(overall_percent):.1f}" if isinstance(overall_percent, (int, float)) else "n/a"),
                    html.Td(f"{float(selected_percent):.1f}" if isinstance(selected_percent, (int, float)) else "n/a"),
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
        dbc.Row(
            [
                dbc.Col(
                    html.P(
                        "This page previews the notebook-style lens explorer using full per-article lens scores when "
                        "the upstream contract provides them, with fallback to legacy lens-score fields.",
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
        _lens_average_figure(article_rows, lens_names, lens_average_rows),
        _article_table(article_rows, effective_lens, n_value),
    )


@callback(
    Output("news-lens-explorer-snapshot-date", "disabled"),
    Input("news-lens-explorer-mode", "value"),
)
def toggle_lens_explorer_snapshot_input(data_mode):
    return data_mode != "snapshot"
