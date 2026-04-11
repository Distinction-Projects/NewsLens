# Agent Guidance for `src/pages/`

## Scope
- Dash UI pages only. Keep page logic thin and push reusable data shaping into `src/services/` when needed by more than one page.
- For lens analytics pages, consume backend-derived `data.derived.lens_views` from `/api/news/stats` before adding any page-local article aggregation.
- For lens correlation pages, consume backend-derived `data.derived.lens_correlations.pair_rankings` and `summary_by_matrix` before deriving pair rankings client-side.
- For lens inventory/metadata UI, consume backend-derived `data.derived.lens_inventory` from `/api/news/stats` before reading raw `data.analysis.lens_summary`.
- For source-tag pages, consume backend-derived `data.derived.source_tag_views` for source/tag ordering and summary metrics before rebuilding counters in page code.
- For data-quality pages, consume backend-derived `data.derived.data_quality` before introducing page-local completeness scans.
- For scoring diagnostics, consume backend-derived `data.derived.score_status` and score count fields (`zero_score_articles`, `unscorable_articles`, etc.) instead of inferring from UI-side heuristics.
- For full payload inspection UIs, consume `/api/news/upstream` rather than piecing together only `summary`/`analysis` from `/api/news/stats`.
- For selector-style pages (for example correlations/source differentiation), prefer `data.derived.*` first and use `data.analysis.*` only as fallback.

## Page conventions
- Every page must register with explicit path:
  - `dash.register_page(__name__, path="/...")`
- Keep layouts deterministic; avoid hidden side effects at import time.
- Reuse shared helpers (`news_page_utils.py`, `src/components/*`) before duplicating logic.

## Route guardrails
- Do not change existing route paths unless requested.
- For new pages, add a clear `/news/...` path and match existing naming style.

## Verification focus
- `python -m unittest tests.test_news_pages -v`
- Run page-specific tests when relevant (for example `tests.test_news_lenses`, `tests.test_news_source_differentiation`, `tests.test_news_source_tag_matrix`).
