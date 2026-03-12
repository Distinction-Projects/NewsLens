# SARIMA Dashboard (Python + Dash)

Interactive Plotly Dash application that guides you through SARIMA modeling for time series forecasting using Python. The current dependency set targets Python 3.11 (works on 3.10–3.12, but 3.11 is recommended locally and on Render).

- Live app: https://gabria1.pythonanywhere.com/
- Original tutorial: [Time Series Data Analysis with SARIMA and Dash](https://medium.com/towards-data-science/time-series-data-analysis-with-sarima-and-dash-f4199c3fc092) on Towards Data Science. Please retain this attribution if you reuse or deploy.

## Workflow in the app
- **Data set up:** start from the built-in AirPassengers dataset (`src/data/AirPassengers.csv`). The app expects two columns (`Time`, `Values`) parsed as dates and numeric data.
- **Stationarity checks:** apply log transforms and differencing, run the Augmented Dickey-Fuller test, and inspect ACF/PACF and Box-Cox plots.
- **Model selection:** run a SARIMA `(p,d,q)(P,D,Q,m)` grid search scored by AIC with train/test split control.
- **Prediction:** fit the selected model, visualize train/test forecasts with confidence intervals, and review residual ACF/PACF.

## Run locally (Python 3.11)
```bash
git clone <your fork of this repo>
cd ML_Sentiment

# macOS / Linux (recommended when available)
python3.11 -m venv .venv
source .venv/bin/activate

# Windows (PowerShell) — preferred if you have the Python launcher
py -3.11 -m venv .venv
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope Process -Force
.\.venv\Scripts\Activate.ps1

# Windows (Command Prompt)
py -3.11 -m venv .venv
.\.venv\Scripts\activate.bat

# If `py` is not available but `python` points to a suitable interpreter
python -m venv .venv
.\.venv\Scripts\Activate.ps1   # PowerShell

pip install --upgrade pip
pip install -r requirements.txt
# Pre-download NLTK data to speed up first run (optional; auto-downloads on startup if missing)
python -m nltk.downloader stopwords punkt wordnet vader_lexicon punkt_tab
# Pre-build cached models and evaluation metrics for faster runtime inference (recommended; done during cloud builds)
python -m src.cache_models
python -m src.app
```

The server runs at http://localhost:8050 by default. Edit `src/app.py` to set `debug=True` while developing if you want auto-reload. The `.venv` folder is gitignored; if you use a different env name, add it to `.gitignore` to keep it out of commits.

### VS Code tasks (macOS/Linux)
If you use VS Code, there is a simple task setup in `.vscode/tasks.json` to automate the local workflow. The `Setup: Full local` task runs automatically on folder open; remove the `runOptions` block in `.vscode/tasks.json` if you want to opt out.
- `Setup: Full local` creates the venv, installs requirements, downloads NLTK data, and builds cached models + metrics.
- `App: Run (Dash)` starts the server with `python -m src.app`.

Windows users should follow the manual commands above.

### Production-style local run
If you want to mirror the DigitalOcean command locally, run:
```bash
gunicorn --chdir src --timeout 600 app:server --bind 0.0.0.0:${PORT:-8050} --worker-tmp-dir ${WORKER_TMP_DIR:-/tmp}
```

### RSS Digest API (read-only consumer)
This app consumes the app-facing precomputed contract JSON from RSS_Feeds and exposes runtime APIs without rebuilding the image for each data update.

Set these environment variables:
- `RSS_DAILY_JSON_URL` (optional): upstream JSON URL. Default:
  `https://raw.githubusercontent.com/Distinction-Projects/RSS_Feeds/main/data/processed/rss_openai_precomputed.json`
- `RSS_HISTORY_JSON_URL_TEMPLATE` (optional): snapshot URL template. Default:
  `https://raw.githubusercontent.com/Distinction-Projects/RSS_Feeds/main/data/history/rss_openai_daily_{date}.json`
  (`{date}` is replaced with `YYYY-MM-DD`)
- `RSS_CACHE_TTL_SECONDS` (optional, default `86400`): in-memory TTL cache duration.
- `RSS_HTTP_TIMEOUT_SECONDS` (optional, default `20`): HTTP timeout for upstream fetches.
- `RSS_MAX_AGE_SECONDS` (optional, default `129600`): freshness SLO for `generated_at` (36 hours).

Available endpoints:
- `GET /api/news/digest/latest`: latest item from the digest feed.
- `GET /api/news/digest`: full/filtered digest list.
- `GET /api/news/stats`: derived source/tag/score/time stats from normalized articles.
- `GET /health/news-freshness`: health check based on payload `generated_at`.

Dash pages for this data:
- `/news/digest`: filterable digest view and latest-card view.
- `/news/stats`: charts/cards for source, tags, score distribution, and daily counts.
- `/news/integration`: CI-oriented runtime checks for endpoint reachability, payload presence, and freshness state.
- `/news/scraped`: grouped-by-source view of raw `articles[].scraped` payloads from the digest.
- `/news/trends`: time-focused trend views (daily counts + publish-hour distribution).
- `/news/sources`: source leaderboard + source score summary table.
- `/news/tags`: top tags + tag density + source-tag heatmap.
- `/news/score-lab`: score histogram + high-score-by-source + score/tag heatmap.
- `/news/raw-json`: raw endpoint payload explorer for debugging and QA.

Optional query params on digest endpoints:
- `date=YYYY-MM-DD`
- `tag=<tag>`
- `source=<source>`
- `limit=<positive-int>` (`/api/news/digest` only)
- `snapshot_date=YYYY-MM-DD` (supported on `/api/news/digest`, `/api/news/digest/latest`, and `/api/news/stats`)
- `refresh=true` (forces a cache refresh)

Filter semantics:
- `date` uses UTC date from parsed `articles[].published`.
- `tag` matches `ai_tags` and `topic_tags` (case-insensitive exact match).
- `source` matches `source.name`, `source.id`, and `feed.name` (case-insensitive contains).

Response metadata includes `source_mode` (`current` or `snapshot`), `snapshot_date` (when set), and resolved `source_url`.

Current mode (`RSS_DAILY_JSON_URL`) uses last-good fallback on upstream failures and reports the fetch error in metadata. Snapshot mode does not fall back to current data; missing snapshot files return `404`.

The client also supports ETag conditional requests (`If-None-Match`) to avoid re-downloading unchanged artifacts.

### Working with data
- The default AirPassengers sample lives in `src/data/AirPassengers.csv`. Replace that file (keep the `Time` and `Values` headers) to experiment with your own series.
- Restart the app after swapping data to ensure the in-memory dataset refreshes.

## Deploy to DigitalOcean
- DigitalOcean App Platform: the included `app.yaml` is a ready-to-deploy spec. Point App Platform at this repo (`Distinction-Projects/ML_Sentiment`, branch `main`), confirm the detected spec, and deploy. Adjust the repo/branch in the manifest if your fork differs. The spec installs requirements, pre-downloads NLTK data, and starts `gunicorn --chdir src --timeout 600 app:server --bind 0.0.0.0:$PORT --worker-tmp-dir ${WORKER_TMP_DIR:-/tmp}` with Python 3.11 on a `basic-xxs` instance. A `.python-version` file pins Python 3.11 for the DO buildpack. `WORKER_TMP_DIR` defaults to `/dev/shm` (set in `app.yaml`) but the command falls back to `/tmp` if that path is absent (e.g., local macOS test).
- Manual commands (if you prefer to enter them in the UI): build `pip install -r requirements.txt && python -m nltk.downloader stopwords punkt wordnet vader_lexicon punkt_tab && python -m src.cache_models`; run `gunicorn --chdir src --timeout 600 app:server --bind 0.0.0.0:$PORT --worker-tmp-dir ${WORKER_TMP_DIR:-/tmp}`.

## Project layout
```
src/
├── app.py               # Dash bootstrap + page/asset config
├── assets/              # Static assets (CSS, etc.)
├── components/          # Shared UI elements (nav, footer)
├── data/                # AirPassengers sample + sentiment training CSV
├── models/              # Cached vectorizer + trained models (generated)
├── pages/               # Multi-page Dash views
└── utils/               # Plot layout helpers, SARIMA utilities
```
Each folder is a Python package (via `__init__.py`) so imports stay stable locally and on DigitalOcean.

![dash_app_step03](https://user-images.githubusercontent.com/57110246/236455995-a98416d9-57f3-4c6e-b41b-0583ba66c86d.gif)
