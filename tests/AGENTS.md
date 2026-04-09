# Agent Guidance for `tests/`

## Scope
- Validate service contracts, API behavior, and page rendering paths.

## Test selection
- Service/data changes:
  - `python -m unittest tests.test_rss_digest -v`
  - `python -m unittest tests.test_news_endpoints -v`
- Page changes:
  - `python -m unittest tests.test_news_pages -v`
  - run page-specific suites touched by the change (for example `tests.test_news_lenses`, `tests.test_news_lens_matrix`, `tests.test_news_lens_correlations`, `tests.test_news_source_differentiation`, `tests.test_news_source_tag_matrix`).
- Full sweep:
  - `python -m unittest discover -s tests -v`

## Conventions
- Keep tests deterministic; prefer fixtures/mocks for external fetches.
- When adding new derived fields or routes, update assertions for both happy-path and fallback behavior.
- Avoid tests that require production credentials or live upstream availability.
