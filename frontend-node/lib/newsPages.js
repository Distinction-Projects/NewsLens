export const NEWS_PAGES = [
  {
    slug: "digest",
    title: "News Digest",
    summary:
      "Browse matched articles quickly and inspect source, date, summary, and per-article analysis controls."
  },
  {
    slug: "stats",
    title: "News Stats",
    summary:
      "Get a high-level snapshot of feed volume, scoring coverage, and score/tag distributions."
  },
  {
    slug: "sources",
    title: "News Sources",
    summary:
      "Compare article volume and scoring coverage across sources."
  },
  {
    slug: "lenses",
    title: "News Lenses",
    summary:
      "Review lens-level score behavior to understand framing dimensions across the corpus."
  },
  {
    slug: "lens-matrix",
    title: "News Lens Matrix",
    summary:
      "Inspect source-by-lens matrix patterns to spot systematic framing differences."
  },
  {
    slug: "lens-correlations",
    title: "News Lens Correlations",
    summary:
      "See which lenses move together and which provide independent signal."
  },
  {
    slug: "lens-pca",
    title: "News Lens PCA",
    summary:
      "View latent lens components that explain the largest variance in the dataset."
  },
  {
    slug: "source-differentiation",
    title: "News Source Differentiation",
    summary:
      "Estimate how separable sources are in lens-score space, including within-topic and within-tag modes."
  },
  {
    slug: "source-effects",
    title: "News Source Effects",
    summary:
      "Compare source effect sizes by lens with pooled, within-topic, and within-tag views."
  },
  {
    slug: "score-lab",
    title: "News Score Lab",
    summary:
      "Run focused scoring diagnostics and inspect model-output behavior."
  },
  {
    slug: "lens-explorer",
    title: "News Lens Explorer",
    summary:
      "Explore article-level lens values and distributions interactively."
  },
  {
    slug: "lens-by-source",
    title: "News Lens by Source",
    summary:
      "Compare each lens side-by-side across sources."
  },
  {
    slug: "lens-stability",
    title: "News Lens Stability",
    summary:
      "Check whether source/lens patterns remain stable under resampling."
  },
  {
    slug: "tags",
    title: "News Tags",
    summary:
      "Analyze tag frequency and source-tag intensity patterns."
  },
  {
    slug: "source-tag-matrix",
    title: "News Source Tag Matrix",
    summary:
      "Inspect source-topic composition to contextualize source comparisons."
  },
  {
    slug: "trends",
    title: "News Trends",
    summary:
      "Track temporal movement in scores, coverage, and source behavior."
  },
  {
    slug: "scraped",
    title: "News Scraped",
    summary:
      "Review raw scraped article payloads and grouped source output."
  },
  {
    slug: "workflow-status",
    title: "News Workflow Status",
    summary:
      "Monitor freshness, scrape/scoring health, and current pipeline status."
  },
  {
    slug: "data-quality",
    title: "News Data Quality",
    summary:
      "Audit missingness, unscorable records, and data quality diagnostics."
  },
  {
    slug: "snapshot-compare",
    title: "News Snapshot Compare",
    summary:
      "Compare current data against a selected historical snapshot."
  },
  {
    slug: "raw-json",
    title: "News Raw JSON",
    summary:
      "Inspect raw endpoint payloads for contract/debug verification."
  },
  {
    slug: "integration",
    title: "News Integration",
    summary:
      "Verify app-to-upstream integration status and runtime contract signals."
  }
];

export function getNewsPage(slug) {
  return NEWS_PAGES.find((entry) => entry.slug === slug) || null;
}
