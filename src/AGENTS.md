# Agent Guidance for `src/`

## Purpose
- Implement app/runtime behavior without breaking page routing or API contracts.

## Key entrypoints
- `app.py`: Dash app creation, explicit page imports, Flask `server`.
- `api/news_endpoints.py`: `/api/news/*` and freshness endpoint behavior.
- `services/rss_digest.py`: upstream JSON fetch/cache/derive logic.

## Constraints
- Keep page autodiscovery disabled (`pages_folder=""`) and maintain explicit page imports.
- Avoid changing semantics of shared metadata keys consumed across pages/endpoints.
- Prefer additive changes for new analytics fields; avoid renaming existing keys.
- For reusable lens analytics, treat `derived.lens_views` in `/api/news/stats` as the canonical backend shape consumed by multiple pages.
- For reusable lens inventory/metadata, treat `derived.lens_inventory` in `/api/news/stats` as the canonical backend shape.
- For reusable source/tag ordering and lookup, treat `derived.source_tag_views` as canonical for pages.
- Keep data-completeness metrics in `derived.data_quality` instead of recomputing per page.

## Common mistakes to avoid
- Editing `src/pages/Distinction.code-workspace` (not runtime code).
- Adding a page without explicit `path=` in `dash.register_page`.
- Coupling page-specific transforms into `rss_digest.py` unless reusable by multiple pages.

## Verification
- `python -m py_compile src/app.py src/api/news_endpoints.py src/services/rss_digest.py src/pages/*.py src/components/*.py`
- `python -m unittest discover -s tests -v`
