# Agent Guidance for `src/services/`

## Scope
- Runtime data acquisition, normalization, caching, and derived analytics for news surfaces.

## Primary file
- `rss_digest.py` is the data contract bridge between `RSS_Feeds` outputs and NewsLens pages/endpoints.

## Contract expectations
- Preserve existing top-level fields expected by:
  - `src/api/news_endpoints.py`
  - `src/pages/news_*`
  - tests under `tests/test_rss_digest.py`, `tests/test_news_endpoints.py`, `tests/test_news_pages.py`
- Add new fields in a backward-compatible way (prefer additive keys).
- Keep reusable lens analytics under `derive_stats(...)->derived.lens_views`:
  - `coverage_mode`
  - `lens_names`
  - `article_rows`
  - `source_rows`
  - `stability_rows`
- Keep reusable lens-correlation views under `derive_stats(...)->derived.lens_correlations`:
  - `lenses`, matrix payloads, `pairwise_counts`
  - additive pair ranking helpers (`pair_rankings`, `summary_by_matrix`) for UI pages
- Keep reusable PCA views under `derive_stats(...)->derived.lens_pca`:
  - `components`, `explained_variance`, `loadings`
  - `variance_drivers`, `article_points`, `source_centroids`
  - stable status/reason keys for insufficient coverage states
- Keep reusable MDS views under `derive_stats(...)->derived.lens_mds`:
  - `dimensions`, `dimension_strength`, `stress`
  - `article_points`, `source_centroids`
  - stable status/reason keys for insufficient coverage states
- Keep reusable lens inventory metadata under `derive_stats(...)->derived.lens_inventory`:
  - `coverage_mode`
  - `items_total`
  - `aggregation`
  - `lenses`
- Keep reusable source/tag view metadata under `derive_stats(...)->derived.source_tag_views`:
  - stable source/tag ordering labels
  - per-source tag rows and summary counters
- Keep reusable completeness metrics under `derive_stats(...)->derived.data_quality`:
  - summary counts
  - field coverage rows

## Implementation guardrails
- Keep network behavior resilient (timeouts, fallback behavior, cache semantics).
- Keep snapshot/current mode semantics explicit and unchanged unless requested.
- Avoid page-specific UI assumptions in service-layer code, but prefer service-side computation for any transformation shared across multiple pages.

## Verification
- `python -m unittest tests.test_rss_digest -v`
- `python -m unittest tests.test_news_endpoints -v`
