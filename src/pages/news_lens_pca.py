from __future__ import annotations

import dash
import dash_bootstrap_components as dbc
import plotly.graph_objects as go
from dash import Input, Output, State, callback, ctx, dcc, html

from src.pages.news_page_utils import api_get, build_status_alert, snapshot_param


dash.register_page(
    __name__,
    path="/news/lens-pca",
    name="News Lens PCA",
    title="NewsLens | News Lens PCA",
)


def _select_lens_pca(data: dict) -> tuple[dict, str]:
    if not isinstance(data, dict):
        return {}, "missing"
    derived = data.get("derived")
    derived_pca = derived.get("lens_pca") if isinstance(derived, dict) else None
    if isinstance(derived_pca, dict):
        return derived_pca, "derived"
    return {}, "missing"


def _select_lens_mds(data: dict) -> tuple[dict, str]:
    if not isinstance(data, dict):
        return {}, "missing"
    derived = data.get("derived")
    derived_mds = derived.get("lens_mds") if isinstance(derived, dict) else None
    if isinstance(derived_mds, dict):
        return derived_mds, "derived"
    return {}, "missing"


def _empty_figure(title: str) -> go.Figure:
    figure = go.Figure()
    figure.update_layout(
        title=title,
        template="plotly_white",
        margin={"l": 30, "r": 20, "t": 60, "b": 40},
    )
    return figure


def _summary_cards(pca_payload: dict) -> list:
    status = str(pca_payload.get("status") or "missing")
    n_articles = pca_payload.get("n_articles")
    n_lenses = pca_payload.get("n_lenses")
    explained = pca_payload.get("explained_variance") if isinstance(pca_payload.get("explained_variance"), list) else []
    pc1 = explained[0] if explained else {}
    pc2 = explained[1] if len(explained) > 1 else {}

    pc1_ratio = pc1.get("explained_variance_ratio")
    pc1_cum = pc1.get("cumulative_variance_ratio")
    pc2_cum = pc2.get("cumulative_variance_ratio")
    cumulative_two = pc2_cum if isinstance(pc2_cum, (int, float)) else pc1_cum

    top_driver = "n/a"
    drivers = pca_payload.get("variance_drivers")
    if isinstance(drivers, list) and drivers:
        first = drivers[0]
        if isinstance(first, dict) and isinstance(first.get("lens"), str):
            top_driver = first["lens"]

    cards = [
        ("Status", status),
        ("Complete Articles", n_articles if isinstance(n_articles, (int, float)) else "n/a"),
        ("Lenses", n_lenses if isinstance(n_lenses, (int, float)) else "n/a"),
        ("PC1 Variance", f"{float(pc1_ratio) * 100:.1f}%" if isinstance(pc1_ratio, (int, float)) else "n/a"),
        ("PC1-2 Cumulative", f"{float(cumulative_two) * 100:.1f}%" if isinstance(cumulative_two, (int, float)) else "n/a"),
        ("Top Variance Driver", top_driver),
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


def _explained_variance_figure(pca_payload: dict) -> go.Figure:
    rows = pca_payload.get("explained_variance") if isinstance(pca_payload.get("explained_variance"), list) else []
    cleaned_rows = [row for row in rows if isinstance(row, dict) and isinstance(row.get("component"), str)]
    if not cleaned_rows:
        return _empty_figure("Explained Variance by Principal Component")

    components = [str(row.get("component")) for row in cleaned_rows]
    explained = [
        float(row.get("explained_variance_ratio")) * 100.0
        if isinstance(row.get("explained_variance_ratio"), (int, float))
        else 0.0
        for row in cleaned_rows
    ]
    cumulative = [
        float(row.get("cumulative_variance_ratio")) * 100.0
        if isinstance(row.get("cumulative_variance_ratio"), (int, float))
        else 0.0
        for row in cleaned_rows
    ]

    figure = go.Figure()
    figure.add_trace(
        go.Bar(
            x=components,
            y=explained,
            name="Explained Variance %",
            marker_color="#0d6efd",
            hovertemplate="Component: %{x}<br>Explained: %{y:.2f}%<extra></extra>",
        )
    )
    figure.add_trace(
        go.Scatter(
            x=components,
            y=cumulative,
            mode="lines+markers",
            name="Cumulative Variance %",
            marker_color="#198754",
            yaxis="y2",
            hovertemplate="Component: %{x}<br>Cumulative: %{y:.2f}%<extra></extra>",
        )
    )
    figure.update_layout(
        title="Explained Variance by Principal Component",
        template="plotly_white",
        xaxis_title="Principal Component",
        yaxis={"title": "Explained Variance %", "rangemode": "tozero"},
        yaxis2={"title": "Cumulative %", "overlaying": "y", "side": "right", "rangemode": "tozero"},
        legend={"orientation": "h", "yanchor": "bottom", "y": 1.02, "xanchor": "right", "x": 1.0},
    )
    return figure


def _article_scatter_figure(pca_payload: dict, color_by: str, max_points: int) -> go.Figure:
    points = pca_payload.get("article_points") if isinstance(pca_payload.get("article_points"), list) else []
    usable = [
        row
        for row in points
        if isinstance(row, dict) and isinstance(row.get("pc1"), (int, float)) and isinstance(row.get("pc2"), (int, float))
    ]
    if not usable:
        return _empty_figure("Article Distribution in PC1/PC2 Space")

    limit = int(max_points) if isinstance(max_points, (int, float)) else 300
    limit = max(limit, 50)
    ranked = sorted(
        usable,
        key=lambda row: (abs(float(row.get("pc1") or 0.0)) + abs(float(row.get("pc2") or 0.0))),
        reverse=True,
    )[:limit]

    grouped: dict[str, list[dict]] = {}
    for row in ranked:
        if color_by == "strongest_lens":
            key = str(row.get("strongest_lens") or "Unknown")
        else:
            key = str(row.get("source") or "Unknown")
        grouped.setdefault(key, []).append(row)

    figure = go.Figure()
    for label, rows in sorted(grouped.items(), key=lambda item: (-len(item[1]), item[0].lower())):
        figure.add_trace(
            go.Scatter(
                x=[float(row["pc1"]) for row in rows],
                y=[float(row["pc2"]) for row in rows],
                mode="markers",
                name=label,
                text=[str(row.get("title") or "Untitled") for row in rows],
                customdata=[
                    [
                        row.get("source"),
                        row.get("strongest_lens"),
                    ]
                    for row in rows
                ],
                hovertemplate=(
                    "Title: %{text}<br>"
                    "PC1: %{x:.3f}<br>"
                    "PC2: %{y:.3f}<br>"
                    "Source: %{customdata[0]}<br>"
                    "Strongest Lens: %{customdata[1]}<extra></extra>"
                ),
                marker={"size": 8, "opacity": 0.75},
            )
        )

    centroids = pca_payload.get("source_centroids") if isinstance(pca_payload.get("source_centroids"), list) else []
    if color_by == "source":
        centroid_rows = [
            row
            for row in centroids
            if isinstance(row, dict) and isinstance(row.get("pc1"), (int, float)) and isinstance(row.get("pc2"), (int, float))
        ]
        if centroid_rows:
            figure.add_trace(
                go.Scatter(
                    x=[float(row["pc1"]) for row in centroid_rows],
                    y=[float(row["pc2"]) for row in centroid_rows],
                    mode="markers+text",
                    name="Source Centroids",
                    text=[str(row.get("source")) for row in centroid_rows],
                    textposition="top center",
                    marker={"symbol": "x", "size": 12, "color": "#111111"},
                    hovertemplate="Source: %{text}<br>PC1: %{x:.3f}<br>PC2: %{y:.3f}<extra></extra>",
                )
            )

    figure.update_layout(
        title="Article Distribution in PC1/PC2 Space",
        template="plotly_white",
        xaxis_title="PC1",
        yaxis_title="PC2",
        legend={"orientation": "v"},
    )
    return figure


def _mds_scatter_figure(mds_payload: dict, color_by: str, max_points: int) -> go.Figure:
    points = mds_payload.get("article_points") if isinstance(mds_payload.get("article_points"), list) else []
    usable = [
        row
        for row in points
        if isinstance(row, dict) and isinstance(row.get("mds1"), (int, float)) and isinstance(row.get("mds2"), (int, float))
    ]
    if not usable:
        return _empty_figure("Article Distribution in MDS1/MDS2 Space")

    limit = int(max_points) if isinstance(max_points, (int, float)) else 300
    limit = max(limit, 50)
    ranked = sorted(
        usable,
        key=lambda row: (abs(float(row.get("mds1") or 0.0)) + abs(float(row.get("mds2") or 0.0))),
        reverse=True,
    )[:limit]

    grouped: dict[str, list[dict]] = {}
    for row in ranked:
        if color_by == "strongest_lens":
            key = str(row.get("strongest_lens") or "Unknown")
        else:
            key = str(row.get("source") or "Unknown")
        grouped.setdefault(key, []).append(row)

    figure = go.Figure()
    for label, rows in sorted(grouped.items(), key=lambda item: (-len(item[1]), item[0].lower())):
        figure.add_trace(
            go.Scatter(
                x=[float(row["mds1"]) for row in rows],
                y=[float(row["mds2"]) for row in rows],
                mode="markers",
                name=label,
                text=[str(row.get("title") or "Untitled") for row in rows],
                customdata=[
                    [
                        row.get("source"),
                        row.get("strongest_lens"),
                    ]
                    for row in rows
                ],
                hovertemplate=(
                    "Title: %{text}<br>"
                    "MDS1: %{x:.3f}<br>"
                    "MDS2: %{y:.3f}<br>"
                    "Source: %{customdata[0]}<br>"
                    "Strongest Lens: %{customdata[1]}<extra></extra>"
                ),
                marker={"size": 8, "opacity": 0.75},
            )
        )

    centroids = mds_payload.get("source_centroids") if isinstance(mds_payload.get("source_centroids"), list) else []
    if color_by == "source":
        centroid_rows = [
            row
            for row in centroids
            if isinstance(row, dict) and isinstance(row.get("mds1"), (int, float)) and isinstance(row.get("mds2"), (int, float))
        ]
        if centroid_rows:
            figure.add_trace(
                go.Scatter(
                    x=[float(row["mds1"]) for row in centroid_rows],
                    y=[float(row["mds2"]) for row in centroid_rows],
                    mode="markers+text",
                    name="Source Centroids",
                    text=[str(row.get("source")) for row in centroid_rows],
                    textposition="top center",
                    marker={"symbol": "x", "size": 12, "color": "#111111"},
                    hovertemplate="Source: %{text}<br>MDS1: %{x:.3f}<br>MDS2: %{y:.3f}<extra></extra>",
                )
            )

    stress = mds_payload.get("stress")
    stress_text = f" (Stress: {float(stress):.3f})" if isinstance(stress, (int, float)) else ""
    figure.update_layout(
        title=f"Article Distribution in MDS1/MDS2 Space{stress_text}",
        template="plotly_white",
        xaxis_title="MDS1",
        yaxis_title="MDS2",
        legend={"orientation": "v"},
    )
    return figure


def _loadings_heatmap_figure(pca_payload: dict) -> go.Figure:
    loadings = pca_payload.get("loadings") if isinstance(pca_payload.get("loadings"), dict) else {}
    components = loadings.get("components") if isinstance(loadings.get("components"), list) else []
    lenses = loadings.get("lenses") if isinstance(loadings.get("lenses"), list) else []
    matrix = loadings.get("matrix") if isinstance(loadings.get("matrix"), list) else []
    if not components or not lenses or not matrix:
        return _empty_figure("PCA Component Loadings")

    normalized_matrix: list[list[float]] = []
    for row in matrix[: len(components)]:
        if not isinstance(row, list):
            continue
        normalized_row = []
        for value in row[: len(lenses)]:
            normalized_row.append(float(value) if isinstance(value, (int, float)) else 0.0)
        if len(normalized_row) < len(lenses):
            normalized_row.extend([0.0] * (len(lenses) - len(normalized_row)))
        normalized_matrix.append(normalized_row)
    if not normalized_matrix:
        return _empty_figure("PCA Component Loadings")

    max_abs = max((abs(value) for row in normalized_matrix for value in row), default=1.0)
    if max_abs <= 0:
        max_abs = 1.0

    figure = go.Figure(
        data=[
            go.Heatmap(
                z=normalized_matrix,
                x=lenses,
                y=components,
                zmin=-max_abs,
                zmax=max_abs,
                zmid=0.0,
                colorscale="RdBu",
                colorbar={"title": "Loading"},
                hovertemplate="Component: %{y}<br>Lens: %{x}<br>Loading: %{z:.4f}<extra></extra>",
            )
        ]
    )
    figure.update_layout(
        title="PCA Component Loadings",
        template="plotly_white",
        xaxis_title="Lens",
        yaxis_title="Principal Component",
    )
    return figure


def _component_loading_figure(pca_payload: dict, component: str | None) -> go.Figure:
    loadings = pca_payload.get("loadings") if isinstance(pca_payload.get("loadings"), dict) else {}
    components = loadings.get("components") if isinstance(loadings.get("components"), list) else []
    lenses = loadings.get("lenses") if isinstance(loadings.get("lenses"), list) else []
    matrix = loadings.get("matrix") if isinstance(loadings.get("matrix"), list) else []
    if not components or not lenses or not matrix:
        return _empty_figure("Selected Component Lens Loadings")

    if component not in components:
        component = str(components[0]) if components else None
    if not component:
        return _empty_figure("Selected Component Lens Loadings")

    component_index = components.index(component)
    if component_index >= len(matrix) or not isinstance(matrix[component_index], list):
        return _empty_figure("Selected Component Lens Loadings")

    pairs = []
    row_values = matrix[component_index]
    for lens_index, lens_name in enumerate(lenses):
        value = row_values[lens_index] if lens_index < len(row_values) else None
        if isinstance(value, (int, float)):
            pairs.append((str(lens_name), float(value)))
    if not pairs:
        return _empty_figure("Selected Component Lens Loadings")

    pairs = sorted(pairs, key=lambda item: abs(item[1]), reverse=True)
    labels = [item[0] for item in pairs]
    values = [item[1] for item in pairs]
    colors = ["#198754" if value >= 0 else "#dc3545" for value in values]

    figure = go.Figure(
        data=[
            go.Bar(
                x=labels,
                y=values,
                marker_color=colors,
                hovertemplate="Lens: %{x}<br>Loading: %{y:.4f}<extra></extra>",
            )
        ]
    )
    figure.update_layout(
        title=f"Lens Loadings for {component}",
        template="plotly_white",
        xaxis_title="Lens",
        yaxis_title="Loading",
    )
    return figure


def _variance_driver_figure(pca_payload: dict, top_n: int = 12) -> go.Figure:
    drivers = pca_payload.get("variance_drivers") if isinstance(pca_payload.get("variance_drivers"), list) else []
    rows = [
        row
        for row in drivers
        if isinstance(row, dict) and isinstance(row.get("lens"), str) and isinstance(row.get("weighted_contribution"), (int, float))
    ]
    if not rows:
        return _empty_figure("Variance Drivers by Lens")

    limit = max(3, min(int(top_n), 25))
    ranked = sorted(rows, key=lambda row: float(row.get("weighted_contribution") or 0.0), reverse=True)[:limit]
    total = sum(float(row.get("weighted_contribution") or 0.0) for row in ranked)
    labels = [str(row.get("lens")) for row in ranked]
    values = [
        (float(row.get("weighted_contribution") or 0.0) / total * 100.0) if total > 0 else 0.0
        for row in ranked
    ]

    figure = go.Figure(
        data=[
            go.Bar(
                x=labels,
                y=values,
                marker_color="#fd7e14",
                hovertemplate="Lens: %{x}<br>Weighted contribution: %{y:.2f}%<extra></extra>",
            )
        ]
    )
    figure.update_layout(
        title="Variance Drivers by Lens",
        template="plotly_white",
        xaxis_title="Lens",
        yaxis_title="Contribution %",
    )
    return figure


def _component_table(pca_payload: dict):
    rows = pca_payload.get("component_summary") if isinstance(pca_payload.get("component_summary"), list) else []
    typed_rows = [row for row in rows if isinstance(row, dict)]
    if not typed_rows:
        return dbc.Alert("No PCA component interpretation rows are available.", color="warning", className="mb-0")

    table_rows = []
    for row in typed_rows:
        component = str(row.get("component") or "n/a")
        explained_ratio = row.get("explained_variance_ratio")
        strongest_loadings = row.get("strongest_loadings") if isinstance(row.get("strongest_loadings"), list) else []
        top_positive = row.get("top_positive") if isinstance(row.get("top_positive"), list) else []
        top_negative = row.get("top_negative") if isinstance(row.get("top_negative"), list) else []

        strongest_text = ", ".join(
            f"{entry.get('lens')} ({float(entry.get('loading')):+.3f})"
            for entry in strongest_loadings[:3]
            if isinstance(entry, dict) and isinstance(entry.get("lens"), str) and isinstance(entry.get("loading"), (int, float))
        ) or "n/a"
        positive_text = ", ".join(
            f"{entry.get('lens')} ({float(entry.get('loading')):+.3f})"
            for entry in top_positive[:3]
            if isinstance(entry, dict) and isinstance(entry.get("lens"), str) and isinstance(entry.get("loading"), (int, float))
        ) or "n/a"
        negative_text = ", ".join(
            f"{entry.get('lens')} ({float(entry.get('loading')):+.3f})"
            for entry in top_negative[:3]
            if isinstance(entry, dict) and isinstance(entry.get("lens"), str) and isinstance(entry.get("loading"), (int, float))
        ) or "n/a"

        table_rows.append(
            html.Tr(
                [
                    html.Td(component),
                    html.Td(f"{float(explained_ratio) * 100:.2f}%" if isinstance(explained_ratio, (int, float)) else "n/a"),
                    html.Td(strongest_text),
                    html.Td(positive_text),
                    html.Td(negative_text),
                ]
            )
        )

    return dbc.Table(
        [
            html.Thead(
                html.Tr(
                    [
                        html.Th("Component"),
                        html.Th("Explained %"),
                        html.Th("Strongest Loadings"),
                        html.Th("Top Positive"),
                        html.Th("Top Negative"),
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
        dcc.Interval(id="news-lens-pca-load", interval=50, n_intervals=0, max_intervals=1),
        dbc.Row([dbc.Col(html.H3("News Lens PCA", className="mb-2"), width=12)]),
        dbc.Row(
            [
                dbc.Col(
                    html.P(
                        "Principal Component Analysis and classical MDS over complete article-lens rows. "
                        "Use this page to inspect variance structure, identify the strongest lens drivers, "
                        "and compare source/article separation across two reduced-dimension projections.",
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
                            id="news-lens-pca-mode",
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
                        dcc.Input(id="news-lens-pca-snapshot-date", type="date", className="form-control", disabled=True),
                    ],
                    md=2,
                ),
                dbc.Col(
                    [
                        dbc.Label("Color by"),
                        dcc.Dropdown(
                            id="news-lens-pca-color-by",
                            options=[
                                {"label": "Source", "value": "source"},
                                {"label": "Strongest Lens", "value": "strongest_lens"},
                            ],
                            value="source",
                            clearable=False,
                        ),
                    ],
                    md=2,
                ),
                dbc.Col(
                    [
                        dbc.Label("Max points"),
                        dcc.Dropdown(
                            id="news-lens-pca-max-points",
                            options=[{"label": str(n), "value": n} for n in (100, 200, 300, 500, 800)],
                            value=300,
                            clearable=False,
                        ),
                    ],
                    md=2,
                ),
                dbc.Col(
                    [
                        dbc.Label("Actions"),
                        dbc.Button("Refresh", id="news-lens-pca-refresh", color="secondary"),
                    ],
                    md=1,
                ),
                dbc.Col(html.Div(id="news-lens-pca-status"), md=3),
            ],
            className="mb-3",
        ),
        dbc.Row(id="news-lens-pca-cards"),
        dbc.Row(
            [
                dbc.Col(dcc.Graph(id="news-lens-pca-explained"), lg=5, className="mb-3"),
                dbc.Col(dcc.Graph(id="news-lens-pca-scatter"), lg=7, className="mb-3"),
            ]
        ),
        dbc.Row([dbc.Col(dcc.Graph(id="news-lens-mds-scatter"), width=12, className="mb-3")]),
        dbc.Row([dbc.Col(dcc.Graph(id="news-lens-pca-drivers"), width=12, className="mb-3")]),
        dbc.Row([dbc.Col(dcc.Graph(id="news-lens-pca-loadings"), width=12, className="mb-3")]),
        dbc.Row(
            [
                dbc.Col(
                    [
                        dbc.Label("Component detail"),
                        dcc.Dropdown(id="news-lens-pca-component", options=[], value=None, clearable=False),
                    ],
                    md=3,
                    className="mb-3",
                )
            ]
        ),
        dbc.Row([dbc.Col(dcc.Graph(id="news-lens-pca-component-figure"), width=12, className="mb-3")]),
        dbc.Row([dbc.Col(html.Div(id="news-lens-pca-table"), width=12)]),
    ],
    fluid=True,
    className="py-4",
)


@callback(
    Output("news-lens-pca-status", "children"),
    Output("news-lens-pca-cards", "children"),
    Output("news-lens-pca-explained", "figure"),
    Output("news-lens-pca-scatter", "figure"),
    Output("news-lens-mds-scatter", "figure"),
    Output("news-lens-pca-drivers", "figure"),
    Output("news-lens-pca-loadings", "figure"),
    Output("news-lens-pca-component", "options"),
    Output("news-lens-pca-component", "value"),
    Output("news-lens-pca-component-figure", "figure"),
    Output("news-lens-pca-table", "children"),
    Input("news-lens-pca-load", "n_intervals"),
    Input("news-lens-pca-refresh", "n_clicks"),
    Input("news-lens-pca-color-by", "value"),
    Input("news-lens-pca-max-points", "value"),
    State("news-lens-pca-component", "value"),
    State("news-lens-pca-mode", "value"),
    State("news-lens-pca-snapshot-date", "value"),
)
def load_news_lens_pca(_load_tick, _refresh_clicks, color_by, max_points, selected_component, data_mode, snapshot_date):
    force_refresh = ctx.triggered_id == "news-lens-pca-refresh"
    status_code, payload = api_get(
        "/api/news/stats",
        {
            "snapshot_date": snapshot_param(data_mode, snapshot_date),
            "refresh": "true" if force_refresh else None,
        },
    )

    if status_code != 200:
        error = payload.get("error", "Unknown error")
        alert = dbc.Alert(f"Stats error ({status_code}): {error}", color="danger")
        empty = _empty_figure("No data")
        return alert, _summary_cards({}), empty, empty, empty, empty, empty, [], None, empty, alert

    meta = payload.get("meta", {})
    data = payload.get("data", {})
    pca_payload, source = _select_lens_pca(data)
    mds_payload, mds_source = _select_lens_mds(data)
    pca_status = str(pca_payload.get("status") or "missing")
    pca_reason = str(pca_payload.get("reason") or "").strip()
    mds_status = str(mds_payload.get("status") or "missing")
    mds_reason = str(mds_payload.get("reason") or "").strip()
    leading_parts = [
        f"PCA source: {source}",
        f"PCA status: {pca_status}",
        f"Complete rows: {pca_payload.get('n_articles', 0)}",
        f"Lenses: {pca_payload.get('n_lenses', 0)}",
        f"Basis: {pca_payload.get('basis', 'n/a')}",
        f"MDS source: {mds_source}",
        f"MDS status: {mds_status}",
    ]
    if pca_reason:
        leading_parts.append(f"PCA reason: {pca_reason}")
    if mds_reason:
        leading_parts.append(f"MDS reason: {mds_reason}")
    status_alert = build_status_alert(meta, leading_parts=leading_parts)

    components = pca_payload.get("components") if isinstance(pca_payload.get("components"), list) else []
    component_options = [{"label": str(component), "value": str(component)} for component in components if isinstance(component, str)]
    option_values = {option["value"] for option in component_options}
    selected_value = selected_component if selected_component in option_values else (component_options[0]["value"] if component_options else None)
    point_limit = int(max_points) if isinstance(max_points, (int, float)) else 300
    color_mode = str(color_by or "source")

    return (
        status_alert,
        _summary_cards(pca_payload),
        _explained_variance_figure(pca_payload),
        _article_scatter_figure(pca_payload, color_mode, point_limit),
        _mds_scatter_figure(mds_payload, color_mode, point_limit),
        _variance_driver_figure(pca_payload),
        _loadings_heatmap_figure(pca_payload),
        component_options,
        selected_value,
        _component_loading_figure(pca_payload, selected_value),
        _component_table(pca_payload),
    )


@callback(
    Output("news-lens-pca-snapshot-date", "disabled"),
    Input("news-lens-pca-mode", "value"),
)
def toggle_news_lens_pca_snapshot_input(data_mode):
    return data_mode != "snapshot"
