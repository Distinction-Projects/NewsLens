# Agent Guidance for NewsLens

## Mission
- Keep the NewsLens app stable as a dual-surface product:
  - local sentiment/model playground
  - RSS/OpenAI news analytics consumer
- Prefer narrow, high-signal changes over cross-cutting refactors.

## Repo map
- `src/app.py`: Dash bootstrap + Flask `server` export.
- `src/pages/`: Dash page modules (explicit `dash.register_page(..., path=...)`).
- `src/services/rss_digest.py`: runtime RSS contract loading, normalization, derived stats.
- `src/api/news_endpoints.py`: digest/stats/freshness endpoints.
- `tests/`: unit/integration tests for services, endpoints, and pages.
- `deploy/droplet/`: droplet bootstrap + `systemd`/`nginx` templates.
- `.github/workflows/deploy-droplet.yml`: deploy-to-droplet pipeline.

## Scope boundaries
- Do not change routing/bootstrap strategy in `src/app.py` unless explicitly asked.
- Do not change model-training assets under `src/data/`/`src/models/` unless task requires it.
- Do not refactor unrelated pages when adding a single page or metric.
- Keep `RSS_Feeds` contract compatibility intact (`src/services/rss_digest.py` consumers rely on it).

## Working strategy
- Start with targeted search:
  - `rg -n "<feature|field|route>" src/services src/api src/pages tests`
  - `rg --files src/pages tests`
- Prefer backend-owned analytics when multiple pages need the same computation:
  - put reusable derivations in `src/services/rss_digest.py`
  - expose via `/api/news/stats` under additive `derived.*` keys
  - prefer canonical backend views:
    - `derived.lens_views`
    - `derived.lens_inventory`
    - `derived.lens_correlations` (including pair rankings/summary)
    - `derived.source_tag_views`
    - `derived.data_quality`
  - keep page modules focused on rendering/filtering, not article-level recomputation
- Prefer the smallest area that can satisfy the task:
  - service/data shape work: `src/services` + `src/api` + related tests
  - UI work: specific `src/pages/*` + `src/components/*` + page tests
  - deploy work: `.github/workflows` or `deploy/droplet`

## Canonical commands
- Setup/runtime:
  - `python3.11 -m venv .venv && source .venv/bin/activate`
  - `pip install -r requirements.txt`
  - `python -m nltk.downloader stopwords punkt wordnet vader_lexicon punkt_tab`
  - `python -m src.cache_models`
  - `python -m src.app`
- Fast validation:
  - `python -m py_compile src/app.py src/api/news_endpoints.py src/services/rss_digest.py src/pages/*.py src/components/*.py`
  - `python -m unittest discover -s tests -v`

## Done criteria
- Changed behavior is covered by existing or updated tests in `tests/`.
- News endpoints/pages still return expected shape for current and snapshot modes.
- No accidental route drift (all changed pages keep explicit `path=`).
- If deploy/workflow changed, include a smoke check result or command used.
