from dash import html, Input, Output, State, callback
import dash_bootstrap_components as dbc
import dash

ANALYSIS_PAGE_ORDER = {
    "Home": 0,
    "Model Evaluation": 1,
    "Test Your Text": 2,
}

NEWS_PAGE_ORDER = {
    "News Digest": 0,
    "News Stats": 1,
    "News Sources": 2,
    "News Lenses": 3,
    "News Lens Matrix": 4,
    "News Lens Correlations": 5,
    "News Lens PCA": 6,
    "News Source Differentiation": 7,
    "News Source Effects": 8,
    "News Score Lab": 9,
    "News Lens Explorer": 10,
    "News Lens by Source": 11,
    "News Lens Stability": 12,
    "News Tags": 13,
    "News Source Tag Matrix": 14,
    "News Trends": 15,
    "News Scraped": 16,
    "News Workflow Status": 17,
    "News Data Quality": 18,
    "News Snapshot Compare": 19,
    "News Raw JSON": 20,
    "News Integration": 21,
}


def _ordered_pages(group_pages, preferred_order):
    return sorted(group_pages, key=lambda page: (preferred_order.get(page.get("name"), 999), page.get("name", "")))


def _grouped_pages():
    pages = list(dash.page_registry.values())
    news_pages = [page for page in pages if str(page.get("path", "")).startswith("/news")]
    analysis_pages = [page for page in pages if page not in news_pages]
    return _ordered_pages(analysis_pages, ANALYSIS_PAGE_ORDER), _ordered_pages(news_pages, NEWS_PAGE_ORDER)


def _nav_links(pages):
    return dbc.Nav(
        [dbc.NavLink(page["name"], active="exact", href=page["path"]) for page in pages],
        vertical=True,
        pills=True,
        class_name="my-nav",
    )


analysis_pages, news_pages = _grouped_pages()

_nav = dbc.Container(
    [
        dbc.Row(
            [
                dbc.Col(
                    [html.Div([html.I(className="fa-solid fa-chart-simple fa-2x")], className="logo")],
                    width=4,
                ),
                dbc.Col([html.H1(["NewsLens"], className="app-brand")], width=8),
            ]
        ),
        dbc.Row(
            [
                dbc.Button(
                    "Analysis",
                    id="nav-analysis-toggle",
                    color="dark",
                    outline=True,
                    class_name="nav-group-toggle w-100 mt-3",
                ),
                dbc.Collapse(
                    _nav_links(analysis_pages),
                    id="nav-analysis-collapse",
                    is_open=True,
                    class_name="mt-2",
                ),
            ]
        ),
        dbc.Row(
            [
                dbc.Button(
                    "News Information",
                    id="nav-news-toggle",
                    color="dark",
                    outline=True,
                    class_name="nav-group-toggle w-100 mt-2",
                ),
                dbc.Collapse(
                    _nav_links(news_pages),
                    id="nav-news-collapse",
                    is_open=True,
                    class_name="mt-2",
                ),
            ]
        ),
    ]
)


@callback(
    Output("nav-analysis-collapse", "is_open"),
    Input("nav-analysis-toggle", "n_clicks"),
    State("nav-analysis-collapse", "is_open"),
    prevent_initial_call=True,
)
def toggle_analysis_nav(_n_clicks, is_open):
    return not is_open


@callback(
    Output("nav-news-collapse", "is_open"),
    Input("nav-news-toggle", "n_clicks"),
    State("nav-news-collapse", "is_open"),
    prevent_initial_call=True,
)
def toggle_news_nav(_n_clicks, is_open):
    return not is_open
