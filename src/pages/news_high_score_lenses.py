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
    redirect_from=["/news/high-score-lenses"],
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


def _legacy_high_score_lens_scores(article: dict, lens_maxima: dict[str, float]) -> dict[str, float]:
    high_score = article.get("high_score")
    if not isinstance(high_score, dict):
        return {}
    lens_scores = high_score.get("lens_scores")
    if not isinstance(lens_scores, dict) or not lens_scores:
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


def _article_rows(articles: list[dict], lens_maxima: dict[str, float]) -> tuple[list[dict], str]:
    rows: list[dict] = []
    data_modes: set[str] = set()
    for article in articles:
        normalized_scores = _full_score_lens_scores(article)
        row_mode = "full"
        if not normalized_scores:
            normalized_scores = _legacy_high_score_lens_scores(article, lens_maxima)
            row_mode = "legacy"

        if not normalized_scores:
            continue

        data_modes.add(row_mode)
        strongest_lens, strongest_percent = max(normalized_scores.items(), key=lambda item: item[1])
        source = article.get("source") if isinstance(article.get("source"), dict) else {}
        score = article.get("score") if isinstance(article.get("score"), dict) else {}
        high_score = article.get("high_score") if isinstance(article.get("high_score"), dict) else {}
        rows.append(
            {
                "title": article.get("title", "Untitled"),
                "source": source.get("name", "Unknown"),
                "published": article.get("published"),
                "overall_percent": score.get("percent")
                if isinstance(score.get("percent"), (int, float))
                else high_score.get("overall_percent"),
                "lens_scores": normalized_scores,
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


def _lens_average_figure(article_rows: list[dict], lens_names: list[str]) -> go.Figure:
    if not article_rows or not lens_names:
        return _empty_figure("Average Lens Percent Across Available Articles")

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


def _summary_cards(article_rows: list[dict], selected_lens: str | None) -> list:
    overall_values = [float(row["overall_percent"]) for row in article_rows if isinstance(row.get("overall_percent"), (int, float))]
    selected_values = [
        float(row["lens_scores"][selected_lens])
        for row in article_rows
        if selected_lens and isinstance(row["lens_scores"].get(selected_lens), (int, float))
    ]
    dominant_counts: defaultdict[str, int] = defaultdict(int)
    for row in article_rows:
        dominant_counts[row["strongest_lens"]] += 1
    dominant_lens = max(dominant_counts.items(), key=lambda item: item[1])[0] if dominant_counts else "n/a"

    cards = [
        ("Articles with Lens Scores", len(article_rows)),
        ("Avg Overall %", f"{(sum(overall_values) / len(overall_values)):.1f}" if overall_values else "n/a"),
        (
            f"Avg {selected_lens} %" if selected_lens else "Avg Selected Lens %",
            f"{(sum(selected_values) / len(selected_values)):.1f}" if selected_values else "n/a",
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
        dcc.Interval(id="news-high-score-lenses-load", interval=50, n_intervals=0, max_intervals=1),
        dbc.Row([dbc.Col(html.H3("News Lens Explorer", className="mb-2"), width=12)]),
        dbc.Row(
            [
                dbc.Col(
                    html.P(
                        "This page previews the notebook-style lens explorer using full per-article lens scores when "
                        "the upstream contract provides them, with fallback to the older high-score subset.",
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
                            id="news-high-score-lenses-mode",
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
                            id="news-high-score-lenses-snapshot-date",
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
                        dcc.Dropdown(id="news-high-score-lenses-lens", options=[], value=None, clearable=False),
                    ],
                    md=3,
                ),
                dbc.Col(
                    [
                        dbc.Label("Top N articles"),
                        dcc.Input(
                            id="news-high-score-lenses-top-n",
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
                        dbc.Button("Refresh", id="news-high-score-lenses-refresh", color="secondary"),
                    ],
                    md=1,
                ),
                dbc.Col(html.Div(id="news-high-score-lenses-status"), md=2),
            ],
            className="mb-3",
        ),
        dbc.Row(id="news-high-score-lenses-cards"),
        dbc.Row(
            [
                dbc.Col(dcc.Graph(id="news-high-score-lenses-selected-graph"), lg=7, className="mb-3"),
                dbc.Col(dcc.Graph(id="news-high-score-lenses-average-graph"), lg=5, className="mb-3"),
            ]
        ),
        dbc.Row([dbc.Col(html.Div(id="news-high-score-lenses-table"), width=12)]),
    ],
    fluid=True,
    className="py-4",
)


@callback(
    Output("news-high-score-lenses-status", "children"),
    Output("news-high-score-lenses-lens", "options"),
    Output("news-high-score-lenses-lens", "value"),
    Output("news-high-score-lenses-cards", "children"),
    Output("news-high-score-lenses-selected-graph", "figure"),
    Output("news-high-score-lenses-average-graph", "figure"),
    Output("news-high-score-lenses-table", "children"),
    Input("news-high-score-lenses-load", "n_intervals"),
    Input("news-high-score-lenses-refresh", "n_clicks"),
    Input("news-high-score-lenses-lens", "value"),
    State("news-high-score-lenses-mode", "value"),
    State("news-high-score-lenses-snapshot-date", "value"),
    State("news-high-score-lenses-top-n", "value"),
)
def load_news_high_score_lenses(_load_tick, _refresh_clicks, selected_lens, data_mode, snapshot_date, top_n):
    force_refresh = ctx.triggered_id == "news-high-score-lenses-refresh"
    common_params = {
        "snapshot_date": snapshot_param(data_mode, snapshot_date),
        "refresh": "true" if force_refresh else None,
    }
    stats_code, stats_payload = api_get("/api/news/stats", common_params)
    digest_code, digest_payload = api_get("/api/news/digest", common_params)
    n_value = int(top_n) if isinstance(top_n, (int, float)) and top_n else 10
    n_value = max(3, min(50, n_value))

    if stats_code != 200 or digest_code != 200:
        stats_error = stats_payload.get("error", "Unknown error")
        digest_error = digest_payload.get("error", "Unknown error")
        empty = _empty_figure("No data")
        alert = dbc.Alert(
            f"High-score lens data error: stats={stats_code} ({stats_error}); digest={digest_code} ({digest_error})",
            color="danger",
        )
        return alert, [], None, _summary_cards([], None), empty, empty, dbc.Alert("No table data.", color="warning")

    meta = digest_payload.get("meta", {})
    analysis = stats_payload.get("data", {}).get("analysis", {})
    lens_summary = analysis.get("lens_summary", {}) if isinstance(analysis, dict) else {}
    lens_maxima = _lens_max_map(lens_summary)
    digest_articles = digest_payload.get("data", []) if isinstance(digest_payload.get("data"), list) else []
    article_rows, coverage_mode = _article_rows(digest_articles, lens_maxima)

    lens_names = list(lens_maxima.keys())
    if not lens_names:
        lens_names = sorted({lens_name for row in article_rows for lens_name in row["lens_scores"]})
    effective_lens = selected_lens if selected_lens in lens_names else (lens_names[0] if lens_names else None)

    return (
        build_status_alert(
            meta,
            leading_parts=[
                f"Articles with lens scores: {len(article_rows)}",
                f"Coverage: {coverage_mode}",
            ],
        ),
        _lens_options(lens_names),
        effective_lens,
        _summary_cards(article_rows, effective_lens),
        _selected_lens_figure(article_rows, effective_lens, n_value),
        _lens_average_figure(article_rows, lens_names),
        _article_table(article_rows, effective_lens, n_value),
    )


@callback(
    Output("news-high-score-lenses-snapshot-date", "disabled"),
    Input("news-high-score-lenses-mode", "value"),
)
def toggle_high_score_snapshot_input(data_mode):
    return data_mode != "snapshot"
