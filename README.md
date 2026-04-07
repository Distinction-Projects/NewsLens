# NewsLens

NewsLens is a Dash application for AI news intelligence and local sentiment analysis.

The repo has two distinct surfaces:

- a local sentiment-model playground for evaluating and testing text classifiers
- a read-only RSS/OpenAI news dashboard fed from the public `RSS_Feeds` repository

The important runtime behavior is that daily upstream JSON updates do not require a new image build. The deployed app keeps the same image and refreshes the RSS contract at runtime.

## What the app includes

### Sentiment model lab
- `/` home page with quick entry points into the app
- `/evaluation` model evaluation across the local corpora
- `/text` ad hoc sentiment testing for user-provided text
- local cached models generated from `src/data/train5.csv`

### RSS / news dashboards
- `/news/digest`
- `/news/stats`
- `/news/sources`
- `/news/tags`
- `/news/score-lab`
- `/news/trends`
- `/news/scraped`
- `/news/workflow-status`
- `/news/snapshot-compare`
- `/news/raw-json`
- `/news/integration`

## Local run

This repo is pinned to Python `3.11` in `.python-version`.

```bash
git clone <your fork or the canonical repo>
cd NewsLens

python3.11 -m venv .venv
source .venv/bin/activate

pip install --upgrade pip
pip install -r requirements.txt
python -m nltk.downloader stopwords punkt wordnet vader_lexicon punkt_tab
python -m src.cache_models
python -m src.app
```

Default local URL:

- `http://localhost:8050`

Pages to check first after startup:

- `http://localhost:8050/`
- `http://localhost:8050/news/digest`
- `http://localhost:8050/news/workflow-status`
- `http://localhost:8050/news/snapshot-compare`

## Production-style local run

If you want the same startup shape as DigitalOcean, run Gunicorn locally:

```bash
PORT=8050 WORKER_TMP_DIR=/tmp gunicorn --chdir src --timeout 600 app:server --bind 0.0.0.0:$PORT --worker-tmp-dir ${WORKER_TMP_DIR}
```

## App bootstrap rules

The bootstrap in `src/app.py` is intentionally opinionated:

- Dash page autodiscovery is disabled with `pages_folder=""`
- pages are imported explicitly from `src.pages`
- the Flask server is exported as `server` for Gunicorn
- page files should set an explicit `path=...` in `dash.register_page(...)`

This is the guardrail that keeps routing consistent between:

- `python -m src.app`
- `gunicorn --chdir src app:server`

Do not switch back to inferred page paths unless you also change the import strategy. That is how routes quietly drift into module-derived URLs like `/src/pages/...`.

## News runtime flow

The RSS/news side of the app is a read-only runtime consumer. The deployment image is not rebuilt for daily news updates.

Runtime flow:

1. `src/services/rss_digest.py` fetches the public JSON contract from `RSS_Feeds`
2. the service normalizes articles, computes lightweight derived stats, and caches the result in memory
3. `src/api/news_endpoints.py` serves digest, stats, and freshness endpoints from that processed bundle
4. Dash news pages render from those endpoints

This means:

- content updates come from upstream JSON refreshes, not code deploys
- image rebuilds are only needed when app code, dependencies, or static assets change
- snapshot mode reads immutable history files by `snapshot_date=YYYY-MM-DD`
- analysis in the consumer is based on the processed upstream bundle, not on writing into a local database

## RSS runtime configuration

The news dashboards consume the public app-facing JSON contract from `RSS_Feeds`.

Environment variables:

- `RSS_DAILY_JSON_URL`
  Default: `https://raw.githubusercontent.com/Distinction-Projects/RSS_Feeds/main/data/processed/rss_openai_precomputed.json`
- `RSS_HISTORY_JSON_URL_TEMPLATE`
  Default: `https://raw.githubusercontent.com/Distinction-Projects/RSS_Feeds/main/data/history/rss_openai_daily_{date}.json`
- `RSS_CACHE_TTL_SECONDS`
  Default: `3600`
- `RSS_HTTP_TIMEOUT_SECONDS`
  Default: `20`
- `RSS_MAX_AGE_SECONDS`
  Default: `129600`

The app supports current mode and snapshot mode. Snapshot mode is selected with `snapshot_date=YYYY-MM-DD` on the existing digest and stats endpoints.

## Runtime API

Available endpoints:

- `GET /api/news/digest`
- `GET /api/news/digest/latest`
- `GET /api/news/stats`
- `GET /health/news-freshness`

Supported digest and stats query params:

- `date=YYYY-MM-DD`
- `tag=<tag>`
- `source=<source>`
- `limit=<positive-int>`
- `snapshot_date=YYYY-MM-DD`
- `refresh=true`

Filter behavior:

- `date` uses the parsed UTC publish date
- `tag` matches `ai_tags` and `topic_tags` with case-insensitive exact match
- `source` matches `source.name`, `source.id`, and `feed.name` with case-insensitive contains
- digest and stats exclude articles that failed scraping

Metadata returned by the news endpoints includes:

- `source_mode`
- `snapshot_date`
- `source_url`
- `input_articles_count`
- `excluded_unscraped_articles`

## Local verification

Useful checks:

```bash
python -m py_compile src/app.py src/api/news_endpoints.py src/services/rss_digest.py src/pages/*.py src/components/*.py
python -m unittest discover -s tests -v
```

If you are offline and NLTK resources have not already been downloaded, run the downloader command above once before starting the app or running tests.

## DigitalOcean deploy

This repo already includes a ready-to-deploy `app.yaml` for DigitalOcean App Platform.

- Repo: `Distinction-Projects/NewsLens`
- Branch: `main`
- Runtime: Python 3.11
- Start command: `gunicorn --chdir src --timeout 600 app:server --bind 0.0.0.0:$PORT --worker-tmp-dir ${WORKER_TMP_DIR:-/tmp}`

The build step installs requirements, downloads NLTK resources, and pre-builds the cached local models:

```bash
pip install --upgrade pip
pip install -r requirements.txt
python -m nltk.downloader stopwords punkt wordnet vader_lexicon punkt_tab
python -m src.cache_models
```

## App Platform vs Droplet

These two DigitalOcean paths are different:

- `app.yaml` is for DigitalOcean App Platform
- `Procfile` is a process command convention and is useful for App Platform style deploys
- a Droplet does not automatically read either file

On a Droplet, you are responsible for:

- installing Python
- creating the virtualenv
- running Gunicorn under `systemd`
- putting `nginx` in front of Gunicorn
- storing runtime env vars on the server

For this repo, the App Platform path is faster. The Droplet path is better if you want to learn Linux service management and own the full runtime.

## DigitalOcean Droplet

If you want the hands-on deployment path, this repo includes a droplet scaffold in `deploy/droplet/`.

Files:

- `deploy/droplet/newslens.service`
- `deploy/droplet/nginx.newslens.conf`
- `deploy/droplet/bootstrap_ubuntu_24_04.sh`
- `.env.example`

Recommended server shape:

- Ubuntu 24.04 LTS
- `nginx` on port `80`
- Gunicorn bound to `127.0.0.1:8000`
- `systemd` service named `newslens`
- repo checked out at `/srv/newslens/app`
- venv at `/srv/newslens/venv`
- env file at `/etc/newslens/newslens.env`

Important detail:

- Ubuntu 24.04 defaults to Python `3.12`
- this repo is currently pinned to Python `3.11`
- on a Droplet, install Python `3.11` explicitly before bootstrapping this app

One reasonable flow on the server:

```bash
sudo mkdir -p /srv/newslens
sudo chown $USER:$USER /srv/newslens
git clone <your repo url> /srv/newslens/app
cd /srv/newslens/app

sudo bash deploy/droplet/bootstrap_ubuntu_24_04.sh
```

After bootstrap:

```bash
sudo systemctl status newslens --no-pager
sudo journalctl -u newslens -n 100 --no-pager
sudo nginx -t
```

If you later add a domain:

```bash
sudo apt-get install -y certbot python3-certbot-nginx
sudo certbot --nginx -d your-domain.example
```

## GitHub Actions deploy to Droplet

This repo includes an automated deploy workflow at:

- `.github/workflows/deploy-droplet.yml`

It runs on push to `main` (and supports manual runs via `workflow_dispatch`) and does:

- rsync current repo contents to `/srv/newslens/app`
- install/update Python requirements in `/srv/newslens/venv`
- restart `newslens` with `systemd`
- run a smoke check against `http://127.0.0.1:8000/news/source-effects`

Required repository secrets:

- `DROPLET_HOST` (example: `64.23.250.112`)
- `DROPLET_USER` (example: `root`)
- `DROPLET_SSH_KEY` (private SSH key for that user)
- `DROPLET_PORT` (optional, defaults to `22`)

## Project layout

```text
src/
├── app.py
├── NewsLens.py
├── api/
├── assets/
├── components/
├── data/
├── models/
├── pages/
├── services/
└── utils/
```

Key pieces:

- `src/app.py`: Dash bootstrap, page registration, Flask server export
- `src/NewsLens.py`: local model training, caching, evaluation helpers
- `src/api/news_endpoints.py`: Flask endpoints for digest, stats, and freshness
- `src/services/rss_digest.py`: upstream JSON fetch, TTL cache, fallback, normalization, stats derivation
- `src/pages/`: Dash pages for both model and news surfaces
