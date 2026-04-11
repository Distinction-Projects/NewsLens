from __future__ import annotations

from collections import defaultdict

import dash
import dash_bootstrap_components as dbc
import plotly.graph_objects as go
from dash import Input, Output, State, callback, ctx, dcc, html

from src.pages.news_page_utils import api_get, build_status_alert, snapshot_param


dash.register_page(
    __name__,
    path="/news/lens-by-source",
    name="News Lens by Source",
    title="NewsLens | News Lens by Source",
)


def _empty_figure(title: str) -> go.Figure:
    figure = go.Figure()
    figure.update_layout(
        title=title,
        template="plotly_white",
        margin={"l": 30, "r": 20, "t": 60, "b": 40},
    )
    return figure


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


def _source_lens_rows(articles: list[dict], lens_maxima: dict[str, float]) -> tuple[list[dict], list[str], str]:
    by_source_lens: dict[str, dict[str, list[float]]] = defaultdict(lambda: defaultdict(list))
    by_source_overall: dict[str, list[float]] = defaultdict(list)
    by_source_count: dict[str, int] = defaultdict(int)

    for article in articles:
        lens_scores = _full_score_lens_scores(article)
        if not lens_scores:
            continue

        source = article.get("source") if isinstance(article.get("source"), dict) else {}
        source_name = str(source.get("name") or "Unknown")
        by_source_count[source_name] += 1

        score = article.get("score") if isinstance(article.get("score"), dict) else {}
        overall_percent = score.get("percent")
        if isinstance(overall_percent, (int, float)):
            by_source_overall[source_name].append(float(overall_percent))

        for lens_name, percent in lens_scores.items():
            if isinstance(percent, (int, float)):
                by_source_lens[source_name][lens_name].append(float(percent))

    lens_names = list(lens_maxima.keys())
    if not lens_names:
        lens_names = sorted(
            {
                lens_name
                for source_values in by_source_lens.values()
                for lens_name in source_values.keys()
            }
        )

    rows = []
    for source_name, count in sorted(by_source_count.items(), key=lambda item: (-item[1], item[0].lower())):
        lens_means: dict[str, float] = {}
        for lens_name in lens_names:
            values = by_source_lens[source_name].get(lens_name, [])
            if values:
                lens_means[lens_name] = sum(values) / len(values)
        overall_values = by_source_overall.get(source_name, [])
        rows.append(
            {
                "source": source_name,
                "article_count": count,
                "overall_avg": (sum(overall_values) / len(overall_values)) if overall_values else None,
                "lens_means": lens_means,
            }
        )

    coverage = "all scored articles" if rows else "no lens data"
    return rows, lens_names, coverage


def _lens_options(lens_names: list[str]) -> list[dict]:
    return [{"label": lens_name, "value": lens_name} for lens_name in lens_names]


def _source_heatmap_figure(source_rows: list[dict], lens_names: list[str], top_n: int) -> go.Figure:
    rows = source_rows[:top_n]
    if not rows or not lens_names:
        return _empty_figure("Average Lens Percent by Source")

    z_values = []
    for row in rows:
        z_values.append([float(row["lens_means"].get(lens_name) or 0.0) for lens_name in lens_names])

    figure = go.Figure(
        data=[
            go.Heatmap(
                z=z_values,
                x=lens_names,
                y=[row["source"] for row in rows],
                zmin=0,
                zmax=100,
                colorscale="YlOrRd",
                colorbar={"title": "Avg Lens %"},
                customdata=[
                    [
                        [
                            row.get("article_count"),
                            f"{float(row.get('overall_avg')):.1f}"
                            if isinstance(row.get("overall_avg"), (int, float))
                            else "n/a",
                        ]
                        for _ in lens_names
                    ]
                    for row in rows
                ],
                hovertemplate=(
                    "Source: %{y}<br>"
                    "Lens: %{x}<br>"
                    "Avg Lens %: %{z:.1f}<br>"
                    "Articles: %{customdata[0]}<br>"
                    "Avg Overall %: %{customdata[1]}<extra></extra>"
                ),
            )
        ]
    )
    figure.update_layout(
        title="Average Lens Percent by Source",
        template="plotly_white",
        xaxis_title="Lens",
        yaxis_title="Source",
    )
    return figure


def _selected_lens_figure(source_rows: list[dict], selected_lens: str | None, top_n: int) -> go.Figure:
    if not source_rows or not selected_lens:
        return _empty_figure("Top Sources by Selected Lens")

    rows = [
        row
        for row in sorted(
            source_rows,
            key=lambda source_row: (
                float(source_row["lens_means"].get(selected_lens) or 0.0),
                int(source_row.get("article_count") or 0),
            ),
            reverse=True,
        )
        if isinstance(row["lens_means"].get(selected_lens), (int, float))
    ][:top_n]
    if not rows:
        return _empty_figure("Top Sources by Selected Lens")

    figure = go.Figure(
        data=[
            go.Bar(
                x=[row["source"] for row in rows],
                y=[row["lens_means"][selected_lens] for row in rows],
                marker_color="#0d6efd",
            )
        ]
    )
    figure.update_layout(
        title=f"Top Sources by {selected_lens}",
        template="plotly_white",
        yaxis={"range": [0, 100]},
        yaxis_title="Avg Lens %",
    )
    return figure


def _summary_cards(source_rows: list[dict], selected_lens: str | None, lens_summary: dict | None = None) -> list:
    summary = lens_summary if isinstance(lens_summary, dict) else {}
    source_count = int(summary.get("source_count")) if isinstance(summary.get("source_count"), (int, float)) else len(source_rows)
    covered_articles = (
        int(summary.get("covered_articles"))
        if isinstance(summary.get("covered_articles"), (int, float))
        else sum(int(row.get("article_count") or 0) for row in source_rows)
    )

    source_overall_avg = summary.get("source_overall_avg")
    if not isinstance(source_overall_avg, (int, float)):
        overall_values = [
            float(row["overall_avg"]) for row in source_rows if isinstance(row.get("overall_avg"), (int, float))
        ]
        source_overall_avg = (sum(overall_values) / len(overall_values)) if overall_values else None

    selected_avg = None
    source_lens_average_rows = summary.get("source_lens_average_rows")
    if selected_lens and isinstance(source_lens_average_rows, list):
        for row in source_lens_average_rows:
            if not isinstance(row, dict):
                continue
            if row.get("lens") == selected_lens and isinstance(row.get("mean"), (int, float)):
                selected_avg = float(row["mean"])
                break
    if selected_avg is None:
        selected_values = [
            float(row["lens_means"][selected_lens])
            for row in source_rows
            if selected_lens and isinstance(row["lens_means"].get(selected_lens), (int, float))
        ]
        selected_avg = (sum(selected_values) / len(selected_values)) if selected_values else None

    cards = [
        ("Sources with Lens Data", source_count),
        ("Avg Source Overall %", f"{float(source_overall_avg):.1f}" if isinstance(source_overall_avg, (int, float)) else "n/a"),
        (
            f"Avg {selected_lens} %" if selected_lens else "Avg Selected Lens %",
            f"{float(selected_avg):.1f}" if isinstance(selected_avg, (int, float)) else "n/a",
        ),
        ("Covered Articles", covered_articles),
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


def _source_table(source_rows: list[dict], selected_lens: str | None, top_n: int):
    if not source_rows or not selected_lens:
        return dbc.Alert("No source lens breakdown is available.", color="warning", className="mb-0")
    rows = [
        row
        for row in sorted(
            source_rows,
            key=lambda source_row: (
                float(source_row["lens_means"].get(selected_lens) or 0.0),
                int(source_row.get("article_count") or 0),
            ),
            reverse=True,
        )
        if isinstance(row["lens_means"].get(selected_lens), (int, float))
    ][:top_n]
    if not rows:
        return dbc.Alert("No rows are available for the selected lens.", color="warning", className="mb-0")

    table_rows = []
    for row in rows:
        overall_avg = row.get("overall_avg")
        table_rows.append(
            html.Tr(
                [
                    html.Td(row["source"]),
                    html.Td(row.get("article_count", 0)),
                    html.Td(f"{float(overall_avg):.1f}" if isinstance(overall_avg, (int, float)) else "n/a"),
                    html.Td(f"{float(row['lens_means'][selected_lens]):.1f}"),
                ]
            )
        )

    return dbc.Table(
        [
            html.Thead(
                html.Tr(
                    [
                        html.Th("Source"),
                        html.Th("Articles"),
                        html.Th("Avg Overall %"),
                        html.Th(f"{selected_lens} Avg %"),
                    ]
                )
            ),
            html.Tbody(table_rows),
        ],
        bordered=True,
        striped=True,
        hover=True,
        responsive=True,
        size="sm",
    )


layout = dbc.Container(
    [
        dcc.Interval(id="news-lens-by-source-load", interval=50, n_intervals=0, max_intervals=1),
        dbc.Row([dbc.Col(html.H3("News Lens by Source", className="mb-2"), width=12)]),
        dbc.Row(
            [
                dbc.Col(
                    html.P(
                        "This page maps average lens performance to sources, using full per-article lens scores when "
                        "available and falling back to legacy lens-score fields.",
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
                            id="news-lens-by-source-mode",
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
                            id="news-lens-by-source-snapshot-date",
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
                        dcc.Dropdown(id="news-lens-by-source-lens", options=[], value=None, clearable=False),
                    ],
                    md=3,
                ),
                dbc.Col(
                    [
                        dbc.Label("Top N sources"),
                        dcc.Input(
                            id="news-lens-by-source-top-n",
                            type="number",
                            min=3,
                            max=50,
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
                        dbc.Button("Refresh", id="news-lens-by-source-refresh", color="secondary"),
                    ],
                    md=1,
                ),
                dbc.Col(html.Div(id="news-lens-by-source-status"), md=2),
            ],
            className="mb-3",
        ),
        dbc.Row(id="news-lens-by-source-cards"),
        dbc.Row(
            [
                dbc.Col(dcc.Graph(id="news-lens-by-source-selected-graph"), lg=5, className="mb-3"),
                dbc.Col(dcc.Graph(id="news-lens-by-source-heatmap"), lg=7, className="mb-3"),
            ]
        ),
        dbc.Row([dbc.Col(html.Div(id="news-lens-by-source-table"), width=12)]),
    ],
    fluid=True,
    className="py-4",
)


@callback(
    Output("news-lens-by-source-status", "children"),
    Output("news-lens-by-source-lens", "options"),
    Output("news-lens-by-source-lens", "value"),
    Output("news-lens-by-source-cards", "children"),
    Output("news-lens-by-source-selected-graph", "figure"),
    Output("news-lens-by-source-heatmap", "figure"),
    Output("news-lens-by-source-table", "children"),
    Input("news-lens-by-source-load", "n_intervals"),
    Input("news-lens-by-source-refresh", "n_clicks"),
    Input("news-lens-by-source-lens", "value"),
    State("news-lens-by-source-mode", "value"),
    State("news-lens-by-source-snapshot-date", "value"),
    State("news-lens-by-source-top-n", "value"),
)
def load_news_lens_by_source(_load_tick, _refresh_clicks, selected_lens, data_mode, snapshot_date, top_n):
    force_refresh = ctx.triggered_id == "news-lens-by-source-refresh"
    common_params = {
        "snapshot_date": snapshot_param(data_mode, snapshot_date),
        "refresh": "true" if force_refresh else None,
    }
    stats_code, stats_payload = api_get("/api/news/stats", common_params)
    n_value = int(top_n) if isinstance(top_n, (int, float)) and top_n else 12
    n_value = max(3, min(50, n_value))

    if stats_code != 200:
        stats_error = stats_payload.get("error", "Unknown error")
        empty = _empty_figure("No data")
        alert = dbc.Alert(
            f"Lens-by-source data error: stats={stats_code} ({stats_error})",
            color="danger",
        )
        return alert, [], None, _summary_cards([], None), empty, empty, dbc.Alert("No table data.", color="warning")

    meta = stats_payload.get("meta", {})
    derived = stats_payload.get("data", {}).get("derived", {})
    lens_views = derived.get("lens_views", {}) if isinstance(derived, dict) else {}
    source_rows = lens_views.get("source_rows", []) if isinstance(lens_views.get("source_rows"), list) else []
    coverage_mode = str(lens_views.get("coverage_mode") or "no lens data")
    lens_summary = lens_views.get("summary", {}) if isinstance(lens_views.get("summary"), dict) else {}
    source_count = int(lens_summary.get("source_count")) if isinstance(lens_summary.get("source_count"), (int, float)) else len(source_rows)
    lens_names = [str(name) for name in lens_views.get("lens_names", []) if isinstance(name, str) and name.strip()]
    if not lens_names:
        lens_names = sorted({lens_name for row in source_rows for lens_name in row.get("lens_means", {}).keys()})
    effective_lens = selected_lens if selected_lens in lens_names else (lens_names[0] if lens_names else None)

    return (
        build_status_alert(
            meta,
            leading_parts=[f"Sources with lens data: {source_count}", f"Coverage: {coverage_mode}"],
        ),
        _lens_options(lens_names),
        effective_lens,
        _summary_cards(source_rows, effective_lens, lens_summary),
        _selected_lens_figure(source_rows, effective_lens, n_value),
        _source_heatmap_figure(source_rows, lens_names, n_value),
        _source_table(source_rows, effective_lens, n_value),
    )


@callback(
    Output("news-lens-by-source-snapshot-date", "disabled"),
    Input("news-lens-by-source-mode", "value"),
)
def toggle_lens_by_source_snapshot_input(data_mode):
    return data_mode != "snapshot"
