# Notebook Migration Status (`openaiapi_testing` -> `NewsLens`)

Source notebooks found in sibling repo:

- `../openaiapi_testing/notebooks/00_workspace_bootstrap.ipynb`
- `../openaiapi_testing/notebooks/01_lens_matrix_playground.ipynb`
- `../openaiapi_testing/notebooks/02_correlation_explorer.ipynb`
- `../openaiapi_testing/notebooks/03_source_patterns.ipynb`

## Coverage Map

| Notebook | Current NewsLens coverage | Status |
|---|---|---|
| `00_workspace_bootstrap.ipynb` | `news_raw_json`, `news_workflow_status`, `news_data_quality`, API-backed data mode/snapshot handling across pages | Covered |
| `01_lens_matrix_playground.ipynb` | `news_lens_matrix`, `news_lenses`, `news_lens_explorer` (`news_high_score_lenses.py`) | Covered |
| `02_correlation_explorer.ipynb` | `news_lens_correlations` (upstream matrix + derived fallback) | Covered |
| `03_source_patterns.ipynb` | `news_lens_by_source`, `news_source_differentiation`, `news_source_tag_matrix`, `news_lens_stability`, `news_source_effects` | Covered |

## Remaining Gaps Worth Building

- None identified from current notebook set.

## Recent Additions

- `News Data Quality` page (`/news/data-quality`) now covers bootstrap-style completeness checks.
- Export endpoint added: `/api/news/export`
  - `artifact=source_tag_matrix|source_score_summary|lens_pair_metrics|source_lens_effects|source_differentiation_summary`
  - `format=csv|json`
- `News Source Effects` page (`/news/source-effects`) adds lens-level source effect sizes and permutation p-values.
- `News Source Differentiation` now falls back to derived stats when upstream differentiation is missing.
