# Poster Figure Decisions

This note records the current decisions for NewsLens poster figures so future
agents can continue the work without rediscovering the same context.

## Current Framing

The poster should present NewsLens as an interdisciplinary method for
computationally assisted interpretive media inquiry. The visual argument should
foreground comparative reading, interpretive plurality, inspectable annotation,
discursive formations, and temporal movement.

Avoid foregrounding visuals that read as business intelligence dashboards,
source rankings, predictive analytics, benchmark reporting, or automated truth
assessment.

## Canonical Generated Materials

The main generated narrative pack is local/generated output:

`data/exports/newslens_narrative_poster_materials`

The curated handoff set is:

`data/exports/selected_poster_figures`

Use:

- `data/exports/selected_poster_figures/pdf` for poster or LaTeX placement.
- `data/exports/selected_poster_figures/svg` for Illustrator, Inkscape, Figma,
  or other vector editing.

`data/exports/` is ignored by git, so generated figures are local artifacts
unless explicitly copied into a tracked poster repository or asset folder.

## Selected Poster Figures

1. `29_lens_plurality_panel`
   - Best central visual.
   - Shows one discourse object opened through multiple interpretive lenses.
   - Should be the largest figure if space permits.

2. `33_two_tag_lens_comparison`
   - Best quantitative "tags as interpretive features" figure.
   - Currently compares two tags with visibly different lens profiles.
   - More readable than the radar version for exact comparison.

3. `31_event_plurality_panel`
   - Best secondary case-study visual.
   - Shows an event cluster as an inspectable comparative object across
     sources, tags, coverage window, and traceability.

4. `34_discourse_constellation`
   - Preferred over the older tag PCA scatter.
   - Should read as discursive formations, not generic clustering.
   - Uses centroid halos rather than star markers.

5. `30_topic_lens_divergence`
   - Strong evidence/methodology visual.
   - Shows tag/topic slices diverging from corpus lens averages.
   - Needs enough poster space to keep row labels and values readable.

6. `36_lens_drift_dumbbell`
   - Best temporal movement figure.
   - Clearer than the older lens drift chart because it shows baseline-to-recent
     movement directly.

7. `08_tag_momentum`
   - Useful as a smaller temporal attention movement figure.
   - Should be framed carefully so it does not read as a popularity ranking.

8. `35_two_tag_lens_fingerprints`
   - Optional visual alternative to `33_two_tag_lens_comparison`.
   - More visually distinctive, but less quantitatively precise because radar
     charts are harder to compare exactly.

## Figures To De-Emphasize

- `02_lens_correlation_heatmap`: useful method support, but too abstract for
  the main poster argument.
- `06_tag_lens_pca_clusters`: replaced by `34_discourse_constellation`.
- `26_lens_drift`: replaced by `36_lens_drift_dumbbell`.
- `32_reduced_daily_lens_scores`: acceptable but lower priority unless extra
  space is available.
- Raw source rankings, article-count charts, dominant-lens frequency charts,
  and uncontextualized source effect sizes should not be foregrounded.

## Current Visual Adjustment Decisions

- Figure `29` and figure `31` should use circular nodes, larger labels, and
  short intentional text. Avoid trailing ellipses or dense paragraph labels.
- Figure `33` should compare two tags with meaningfully different profiles,
  not near-identical tags.
- Figure `30` should show multiple tags/topics rather than one oversized row.
- Figure `34` should avoid dated centroid/star markers and use modern cluster
  annotation.
- Figure `08` should use color only when the color encoding is labeled and
  meaningful.

## Discursive Formation Labeling

Figure `34_discourse_constellation` uses weighted k-means over tag lens-profile
positions to form tag groups. GPT is used only to name those groups, not to
cluster them or interpret geometry.

The reviewed label artifact is:

`data/exports/selected_poster_figures/tag_cluster_labels_gpt4o.json`

The GPT labeling prompt supplies only tag labels and article counts for each
cluster. It intentionally excludes PCA coordinates, source information, article
text, and conversation context. The current labels were generated with `gpt-4o`
and then lightly edited for poster legibility:

- `Geopolitical Security`
- `Domestic Governance`
- `Global Rights`
- `Institutional Security`
- `Public Memory`
- `Education`

Reuse the reviewed labels when regenerating poster figures:

```bash
.venv/bin/python -m src.analytics.export_poster_figures \
  --stats-url http://64.23.250.112/api/news/stats \
  --preset poster-narrative \
  --tag-cluster-labels-json data/exports/selected_poster_figures/tag_cluster_labels_gpt4o.json \
  --output-dir data/exports/newslens_narrative_poster_materials
```

Only regenerate GPT labels when the tag PCA/tag cluster input changes
substantially.

## Label Standards

- Prefer `annotation value`, `lens profile`, `discourse object`, `interpretive
  feature`, `formation`, and `comparative reading`.
- Avoid poster-facing labels such as `PC1`, `PC2`, `score matrix`, `source
  ranking`, `prediction`, `classifier`, and `truth detection`.
- Do not use trailing ellipses in visible labels. Shorten labels by choosing
  fewer words rather than showing truncated text.
- If color encodes meaning, label the meaning in the figure. If color is only
  visual grouping, avoid implying a good/bad scale.
- Event-cluster figures should describe what is inspectable: sources, tags,
  coverage window, and retained records. Do not expose low-level article IDs or
  embedding mechanics in poster-facing labels.

## Useful Regeneration Command

```bash
.venv/bin/python -m src.analytics.export_poster_figures \
  --stats-url http://64.23.250.112/api/news/stats \
  --preset poster-narrative \
  --output-dir data/exports/newslens_narrative_poster_materials
```

After regenerating, recopy the selected figures into:

`data/exports/selected_poster_figures`
