from __future__ import annotations

from collections import Counter

import dash
import dash_bootstrap_components as dbc
import plotly.graph_objects as go
from dash import Input, Output, State, callback, ctx, dcc, html

from src.pages.news_page_utils import api_get, build_status_alert, snapshot_param


dash.register_page(
    __name__,
    path="/news/source-tag-matrix",
    name="News Source Tag Matrix",
    title="NewsLens | News Source Tag Matrix",
)


def _empty_figure(title: str) -> go.Figure:
    figure = go.Figure()
    figure.update_layout(title=title, template="plotly_white", margin={"l": 30, "r": 20, "t": 60, "b": 40})
    return figure


def _top_labels(source_tag_matrix: list[dict], top_sources: int, top_tags: int) -> tuple[list[str], list[str]]:
    source_counter: Counter[str] = Counter()
    tag_counter: Counter[str] = Counter()
    for row in source_tag_matrix:
        source = str(row.get("source", "Unknown"))
        tag = str(row.get("tag", "")).strip()
        count = int(row.get("count", 0) or 0)
        source_counter[source] += count
        if tag:
            tag_counter[tag] += count

    source_labels = [label for label, _count in source_counter.most_common(top_sources)]
    tag_labels = [label for label, _count in tag_counter.most_common(top_tags)]
    return source_labels, tag_labels


def _top_labels_from_totals(source_totals: list[dict], tag_totals: list[dict], top_sources: int, top_tags: int) -> tuple[list[str], list[str]]:
    source_labels = [
        str(row.get("source")).strip()
        for row in source_totals
        if isinstance(row, dict) and str(row.get("source")).strip() and isinstance(row.get("count"), (int, float))
    ][:top_sources]
    tag_labels = [
        str(row.get("tag")).strip()
        for row in tag_totals
        if isinstance(row, dict) and str(row.get("tag")).strip() and isinstance(row.get("count"), (int, float))
    ][:top_tags]
    return source_labels, tag_labels


def _matrix_values(source_tag_matrix: list[dict], source_labels: list[str], tag_labels: list[str]) -> list[list[int]]:
    value_map = {
        (str(row.get("source", "Unknown")), str(row.get("tag", "")).strip()): int(row.get("count", 0) or 0)
        for row in source_tag_matrix
    }
    z_values = []
    for source in source_labels:
        z_values.append([value_map.get((source, tag), 0) for tag in tag_labels])
    return z_values


def _source_tag_heatmap(
    source_tag_matrix: list[dict],
    top_sources: int,
    top_tags: int,
    source_labels: list[str] | None = None,
    tag_labels: list[str] | None = None,
) -> go.Figure:
    effective_source_labels = list(source_labels or [])
    effective_tag_labels = list(tag_labels or [])
    if not effective_source_labels or not effective_tag_labels:
        effective_source_labels, effective_tag_labels = _top_labels(source_tag_matrix, top_sources, top_tags)
    source_labels = effective_source_labels
    tag_labels = effective_tag_labels
    if not source_labels or not tag_labels:
        return _empty_figure("Source x Tag Matrix")
    z_values = _matrix_values(source_tag_matrix, source_labels, tag_labels)
    figure = go.Figure(
        data=[
            go.Heatmap(
                z=z_values,
                x=tag_labels,
                y=source_labels,
                colorscale="Blues",
                colorbar={"title": "Count"},
                hovertemplate="Source: %{y}<br>Tag: %{x}<br>Count: %{z}<extra></extra>",
            )
        ]
    )
    figure.update_layout(title="Source x Tag Matrix", template="plotly_white")
    return figure


def _source_tag_counts(
    source_tag_matrix: list[dict],
    source_name: str | None,
    top_n: int,
    source_tag_lookup: dict[str, list[dict]] | None = None,
) -> list[tuple[str, int]]:
    if not source_name:
        return []

    if isinstance(source_tag_lookup, dict):
        source_rows = source_tag_lookup.get(source_name, [])
        if isinstance(source_rows, list) and source_rows:
            rows = [
                (str(row.get("tag", "")).strip(), int(row.get("count", 0) or 0))
                for row in source_rows
                if isinstance(row, dict) and str(row.get("tag", "")).strip() and str(row.get("tag", "")).strip().lower() != "general"
            ]
            rows.sort(key=lambda item: (-item[1], item[0].lower()))
            return rows[:top_n]

    rows: list[tuple[str, int]] = []
    for row in source_tag_matrix:
        source = str(row.get("source", "Unknown"))
        tag = str(row.get("tag", "")).strip()
        count = int(row.get("count", 0) or 0)
        if source != source_name or not tag or tag.lower() == "general":
            continue
        rows.append((tag, count))
    rows.sort(key=lambda item: (-item[1], item[0].lower()))
    return rows[:top_n]


def _selected_source_tag_figure(
    source_tag_matrix: list[dict],
    source_name: str | None,
    top_n: int,
    source_tag_lookup: dict[str, list[dict]] | None = None,
) -> go.Figure:
    rows = _source_tag_counts(source_tag_matrix, source_name, top_n, source_tag_lookup)
    if not rows:
        return _empty_figure("Top Tags for Selected Source")
    figure = go.Figure(
        data=[
            go.Bar(
                x=[count for _tag, count in rows],
                y=[tag for tag, _count in rows],
                orientation="h",
                marker_color="#198754",
            )
        ]
    )
    figure.update_layout(
        title=f"Top Tags for {source_name}",
        template="plotly_white",
        yaxis={"autorange": "reversed"},
        xaxis_title="Count",
    )
    return figure


def _source_options(source_labels: list[str]) -> list[dict]:
    return [{"label": source, "value": source} for source in source_labels]


def _summary_cards(
    source_labels: list[str],
    tag_labels: list[str],
    source_tag_matrix: list[dict],
    source_tag_summary: dict | None = None,
) -> list:
    summary = source_tag_summary if isinstance(source_tag_summary, dict) else {}
    non_zero_cells = (
        int(summary.get("non_zero_cells"))
        if isinstance(summary.get("non_zero_cells"), (int, float))
        else sum(1 for row in source_tag_matrix if int(row.get("count", 0) or 0) > 0)
    )
    matrix_rows = (
        int(summary.get("matrix_rows"))
        if isinstance(summary.get("matrix_rows"), (int, float))
        else len(source_tag_matrix)
    )
    cards = [
        ("Sources in View", len(source_labels)),
        ("Tags in View", len(tag_labels)),
        ("Non-zero Cells", non_zero_cells),
        ("Matrix Rows", matrix_rows),
    ]
    return [
        dbc.Col(
            dbc.Card(
                dbc.CardBody([html.P(label, className="text-muted mb-1"), html.H4(str(value), className="mb-0")]),
                className="shadow-sm",
            ),
            md=3,
            className="mb-3",
        )
        for label, value in cards
    ]


def _source_tag_table(
    source_tag_matrix: list[dict],
    source_name: str | None,
    top_n: int,
    source_tag_lookup: dict[str, list[dict]] | None = None,
):
    rows = _source_tag_counts(source_tag_matrix, source_name, top_n, source_tag_lookup)
    if not rows:
        return dbc.Alert("No tags are available for the selected source.", color="warning", className="mb-0")
    return dbc.Table(
        [
            html.Thead(html.Tr([html.Th("Tag"), html.Th("Count")])),
            html.Tbody([html.Tr([html.Td(tag), html.Td(count)]) for tag, count in rows]),
        ],
        bordered=True,
        striped=True,
        hover=True,
        responsive=True,
        size="sm",
    )


layout = dbc.Container(
    [
        dcc.Interval(id="news-source-tag-load", interval=50, n_intervals=0, max_intervals=1),
        dbc.Row([dbc.Col(html.H3("News Source Tag Matrix", className="mb-2"), width=12)]),
        dbc.Row(
            [
                dbc.Col(
                    html.P(
                        "This page is a focused view of source-tag interaction intensity from the derived "
                        "source_tag_matrix aggregate.",
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
                            id="news-source-tag-mode",
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
                        dcc.Input(id="news-source-tag-snapshot-date", type="date", className="form-control", disabled=True),
                    ],
                    md=2,
                ),
                dbc.Col(
                    [
                        dbc.Label("Top Sources"),
                        dcc.Input(id="news-source-tag-top-sources", type="number", min=3, max=30, step=1, value=10, className="form-control"),
                    ],
                    md=2,
                ),
                dbc.Col(
                    [
                        dbc.Label("Top Tags"),
                        dcc.Input(id="news-source-tag-top-tags", type="number", min=5, max=40, step=1, value=15, className="form-control"),
                    ],
                    md=2,
                ),
                dbc.Col(
                    [
                        dbc.Label("Actions"),
                        dbc.Button("Refresh", id="news-source-tag-refresh", color="secondary"),
                    ],
                    md=2,
                ),
                dbc.Col(html.Div(id="news-source-tag-status"), md=2),
            ],
            className="mb-3",
        ),
        dbc.Row(
            [
                dbc.Col(
                    [
                        dbc.Label("Selected Source"),
                        dcc.Dropdown(id="news-source-tag-selected-source", options=[], value=None, clearable=False),
                    ],
                    md=4,
                ),
            ],
            className="mb-3",
        ),
        dbc.Row(id="news-source-tag-cards"),
        dbc.Row(
            [
                dbc.Col(dcc.Graph(id="news-source-tag-heatmap"), lg=8, className="mb-3"),
                dbc.Col(dcc.Graph(id="news-source-tag-selected-graph"), lg=4, className="mb-3"),
            ]
        ),
        dbc.Row([dbc.Col(html.Div(id="news-source-tag-table"), width=12)]),
    ],
    fluid=True,
    className="py-4",
)


@callback(
    Output("news-source-tag-status", "children"),
    Output("news-source-tag-selected-source", "options"),
    Output("news-source-tag-selected-source", "value"),
    Output("news-source-tag-cards", "children"),
    Output("news-source-tag-heatmap", "figure"),
    Output("news-source-tag-selected-graph", "figure"),
    Output("news-source-tag-table", "children"),
    Input("news-source-tag-load", "n_intervals"),
    Input("news-source-tag-refresh", "n_clicks"),
    Input("news-source-tag-selected-source", "value"),
    State("news-source-tag-mode", "value"),
    State("news-source-tag-snapshot-date", "value"),
    State("news-source-tag-top-sources", "value"),
    State("news-source-tag-top-tags", "value"),
)
def load_news_source_tag_matrix(
    _load_tick,
    _refresh_clicks,
    selected_source,
    data_mode,
    snapshot_date,
    top_sources,
    top_tags,
):
    force_refresh = ctx.triggered_id == "news-source-tag-refresh"
    source_limit = int(top_sources) if isinstance(top_sources, (int, float)) and top_sources else 10
    tag_limit = int(top_tags) if isinstance(top_tags, (int, float)) and top_tags else 15
    source_limit = max(3, min(30, source_limit))
    tag_limit = max(5, min(40, tag_limit))

    status_code, payload = api_get(
        "/api/news/stats",
        {
            "snapshot_date": snapshot_param(data_mode, snapshot_date),
            "refresh": "true" if force_refresh else None,
        },
    )

    if status_code != 200:
        error = payload.get("error", "Unknown error")
        empty = _empty_figure("No data")
        alert = dbc.Alert(f"Stats error ({status_code}): {error}", color="danger")
        return alert, [], None, _summary_cards([], [], []), empty, empty, alert

    meta = payload.get("meta", {})
    derived = payload.get("data", {}).get("derived", {})
    chart_aggregates = derived.get("chart_aggregates", {})
    source_tag_matrix = chart_aggregates.get("source_tag_matrix", [])
    source_totals = chart_aggregates.get("source_tag_totals", [])
    tag_totals = chart_aggregates.get("tag_totals", [])
    source_tag_views = derived.get("source_tag_views", {}) if isinstance(derived.get("source_tag_views"), dict) else {}
    source_tag_summary = source_tag_views.get("summary", {}) if isinstance(source_tag_views.get("summary"), dict) else {}
    source_tag_lookup = {
        str(row.get("source")).strip(): row.get("tags")
        for row in source_tag_views.get("source_rows", [])
        if isinstance(row, dict) and str(row.get("source")).strip() and isinstance(row.get("tags"), list)
    }
    source_labels = [
        str(label).strip()
        for label in source_tag_views.get("source_labels", [])
        if isinstance(label, str) and label.strip()
    ][:source_limit]
    tag_labels = [
        str(label).strip()
        for label in source_tag_views.get("tag_labels", [])
        if isinstance(label, str) and label.strip()
    ][:tag_limit]
    if not source_labels or not tag_labels:
        source_labels, tag_labels = _top_labels_from_totals(source_totals, tag_totals, source_limit, tag_limit)
    if not source_labels or not tag_labels:
        source_labels, tag_labels = _top_labels(source_tag_matrix, source_limit, tag_limit)
    effective_source = selected_source if selected_source in source_labels else (source_labels[0] if source_labels else None)

    return (
        build_status_alert(meta, leading_parts=[f"Sources: {len(source_labels)}", f"Tags: {len(tag_labels)}"]),
        _source_options(source_labels),
        effective_source,
        _summary_cards(source_labels, tag_labels, source_tag_matrix, source_tag_summary),
        _source_tag_heatmap(source_tag_matrix, source_limit, tag_limit, source_labels, tag_labels),
        _selected_source_tag_figure(source_tag_matrix, effective_source, tag_limit, source_tag_lookup),
        _source_tag_table(source_tag_matrix, effective_source, tag_limit, source_tag_lookup),
    )


@callback(
    Output("news-source-tag-snapshot-date", "disabled"),
    Input("news-source-tag-mode", "value"),
)
def toggle_source_tag_snapshot_input(data_mode):
    return data_mode != "snapshot"
