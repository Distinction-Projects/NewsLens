# NewsLens Backlog

This document tracks larger plans that are worth preserving but do not need to block the current implementation stream. Keep items concrete enough that they can become tickets or implementation plans later.

## Near-Term Product Polish

- Finish the frontend visual hierarchy pass across the remaining secondary news pages.
- Standardize chart/table section headers on every `/news/*` renderer.
- Add consistent unavailable-data, low-sample, and API-error panels across all analytics pages.
- Tighten responsive behavior for dense tables, filter controls, and Plotly charts on mobile widths.
- Review public copy and remove any remaining internal migration language.

## Group Latent-Space Analytics

Goal: make tags, topics, and sources inspectable as moving groups inside the shared lens PCA/MDS space.

### Backend Derivations

- Add `derived.group_latent_space`.
- Support group types: `source`, `topic`, and `tag`.
- Use the existing global `derived.lens_pca.article_points` and `derived.lens_mds.article_points` as the coordinate basis.
- Compute group centroids in PCA space: `pc1`, `pc2`, and `pc3` where available.
- Compute group centroids in MDS space: `mds1` and `mds2`.
- Compute group dispersion in PCA and MDS space.
- Compute group article counts, source counts, topic counts, and tag counts.
- Compute date coverage: `date_start`, `date_end`, and number of active buckets.
- Compute top lens deviations from corpus mean for each group.
- Compute nearest and farthest groups by centroid distance.
- Add low-sample flags for groups under a configurable threshold.
- Add summary fields for analyzed, unavailable, and low-sample group counts.
- Add config fields:
  - `min_articles_per_group`
  - `max_groups_per_type`
  - `basis`
  - `group_types`

### Temporal Movement

- Add `derived.group_temporal_latent_space`.
- Use weekly buckets by default to reduce daily noise.
- Support future bucket options: `day`, `week`, and `month`.
- For each group and bucket, compute:
  - article count
  - corpus share
  - PCA centroid
  - MDS centroid
  - dispersion
  - dominant lens deviations
  - source mix
- Compute path summaries:
  - total movement distance
  - largest jump
  - start centroid
  - end centroid
  - direction vector
  - coverage gaps
- Flag sparse buckets and unstable paths.

### Popularity Trends

- Add `derived.group_popularity_trends`.
- Compute raw counts and corpus share by time bucket for sources, topics, and tags.
- Compute rolling averages.
- Compute recent-vs-baseline deltas.
- Compute rank changes over time.
- Identify fastest rising groups.
- Identify fastest falling groups.
- Identify persistent high-volume groups.
- Identify emerging and fading groups.
- Keep popularity movement distinct from framing movement in output naming.

### Group Clustering

- Add `derived.group_clusters`.
- Cluster source, topic, and tag centroids separately.
- Start with deterministic threshold or agglomerative clustering over centroid coordinates and lens-deviation vectors.
- Avoid a heavy clustering dependency unless the current deterministic approach is insufficient.
- For each cluster, compute:
  - cluster id
  - group members
  - cluster centroid
  - representative groups
  - dominant lens deviations
  - average dispersion
  - nearest cluster
- Label clusters from lens deviations using deterministic text, not an LLM.

### Frontend Views

- Add `/news/group-latent-space`.
- Add the route to `frontend-node/lib/newsPages.js`.
- Add view modes:
  - `Centroids`
  - `Movement`
  - `Popularity`
  - `Clusters`
- Add group controls:
  - group type: `Source`, `Topic`, `Tag`
  - group selector/search
  - time bucket selector
  - minimum article threshold
- Build visuals:
  - tag constellation: tag centroids sized by popularity and colored by cluster
  - source map: source centroids with dispersion rings
  - topic drift trails: weekly topic centroid paths
  - selected-group article cloud
  - selected-group popularity timeline
  - selected-group centroid path
  - lens-deviation bar chart
  - nearest-neighbor table
  - cluster membership table
- Add links from:
  - `/news/tags`
  - `/news/source-tag-matrix`
  - `/news/lens-pca`
  - `/news/trends`

### Interpretability Guardrails

- Keep every group view in the shared global PCA/MDS space.
- Do not run separate PCA spaces per group as the primary comparison view.
- Show sample size and dispersion near centroid charts.
- Show component loading context beside PCA views.
- Use existing `latent_space_stability` to flag unstable axes.
- Label pooled source comparisons as topic-confounded where relevant.
- Avoid quality claims; use language like framing pattern, lens-space position, coverage mix, and source/tag/topic composition.

### Tests

- Unit test source centroid derivation.
- Unit test tag centroid derivation with multi-tag duplication.
- Unit test topic centroid derivation with untagged bucket behavior.
- Unit test nearest-neighbor ordering.
- Unit test low-sample group flags.
- Unit test weekly bucket assignment.
- Unit test sparse temporal buckets.
- Unit test popularity rising/falling detection.
- Endpoint test that `/api/news/stats` includes `derived.group_latent_space`.
- Snapshot test that precomputed stats include group latent-space summaries.
- Frontend smoke test for `/news/group-latent-space`.

## Backend Analysis Hardening

- Persist derived analytics snapshots in Postgres once JSON-vs-DB parity is stable.
- Add richer FDR summaries to all lens/source effect pages.
- Add stronger drift diagnostics by topic and tag.
- Add event-controlled temporal comparisons.
- Add drilldown from aggregate rows to article/rubric/evidence records.
- Add data-quality warnings directly to affected frontend views.

## Supabase/Postgres Cutover

- Keep `NEWS_DATA_BACKEND=json` until parity checks pass.
- Finish JSON-to-Postgres parity tests for digest, stats, and export endpoints.
- Move any remaining runtime table creation into migrations.
- Make `python -m src.ingest.rss_to_postgres --source current --refresh-derived` the canonical import job.
- Switch production to `NEWS_DATA_BACKEND=postgres` after migrations, import, and smoke checks pass.

## Deployment and Operations

- Keep GitHub Actions as the canonical droplet deploy path.
- Deploy in order: sync, install, migrate, import, build, restart FastAPI, restart Next.js, smoke-check.
- Keep Dash out of public routing once Next parity is accepted.
- Add production smoke checks for the most important chart-heavy pages.
- Rotate exposed credentials before any production hardening milestone.

## Future Research Features

- Compare all-coverage source centroids against same-event source centroids.
- Add event-level timelines for recurring stories.
- Add topic-controlled popularity trends.
- Add tag/topic/source co-movement views.
- Add export artifacts for group latent-space and temporal group paths.
- Add annotation notes for known prompt/model/schema changes so drift can be interpreted correctly.
- Add one detail page per lens, likely under `/news/lenses/[lens]` or `/news/lens/:slug`.
  - Explain the lens definition from the rubric: name, questions, semantic classes, expected question count, score range, and any interpretation notes.
  - Show summary stats: article coverage, mean/median/stddev, score distribution, high/low examples, missingness, source/topic/tag breakdowns, and time trend.
  - Compare to other lenses: strongest correlations, weakest/independent lenses, PCA loading contribution, covariance/correlation table rows, and overlap in top-scoring articles.
  - Include source/topic/tag views for the selected lens: source means/effect sizes, topic-controlled differences, tag-controlled differences, and event-controlled differences when available.
  - Link back to related aggregate pages: lens matrix, lens correlations, lens PCA, lens explorer, lens by source, and lens stability.
