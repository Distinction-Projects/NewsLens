import importlib
import pkgutil
import sys
from pathlib import Path

import dash
import dash_bootstrap_components as dbc
from dash import Dash, dcc

BASE_DIR = Path(__file__).resolve().parent
REPO_ROOT = BASE_DIR.parent
ASSETS_DIR = BASE_DIR / "assets"

if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


def _register_pages() -> None:
    """Import pages through the src.pages package and sync their layouts into Dash.

    We intentionally disable Dash's filesystem page discovery and import pages
    through ``src.pages`` ourselves so the module namespace is stable in both
    local ``python -m src.app`` runs and ``gunicorn --chdir src app:server``.
    Because these modules are imported explicitly, page files should define an
    explicit ``path=...`` in ``dash.register_page`` rather than relying on
    inferred module-name paths.
    """
    import src.pages as pages_package

    package_prefix = f"{pages_package.__name__}."
    for module_info in pkgutil.iter_modules(pages_package.__path__, package_prefix):
        module = importlib.import_module(module_info.name)
        page = dash.page_registry.get(module_info.name)
        if page and hasattr(module, "layout"):
            page["layout"] = getattr(module, "layout")
            page["supplied_layout"] = getattr(module, "layout")


app = Dash(
    __name__,
    use_pages=True,
    assets_folder=str(ASSETS_DIR),
    # Pages are imported through _register_pages() to keep module names stable.
    pages_folder="",
    external_stylesheets=[dbc.themes.BOOTSTRAP, dbc.icons.FONT_AWESOME],
    suppress_callback_exceptions=True,
    prevent_initial_callbacks=True,
)

_register_pages()
server = app.server

from src.api.news_endpoints import register_news_endpoints

register_news_endpoints(server)

from src.components.footer import _footer
from src.components.nav import _nav

app.layout = dbc.Container(
    [
        dbc.Row(
            [
                dbc.Col([_nav], width=2),
                dbc.Col([dbc.Row([dash.page_container])], width=10),
            ]
        ),
        dbc.Row(
            [
                dbc.Col([], width=2),
                dbc.Col([dbc.Row([_footer])], width=10),
            ]
        ),
        dcc.Store(id="browser-memo", data={}, storage_type="session"),
    ],
    fluid=True,
)

if __name__ == "__main__":
    app.run_server(debug=False, host="0.0.0.0")
