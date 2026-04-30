import { render as renderDataQuality } from "./data-quality";
import { render as renderDigest } from "./digest";
import { render as renderEventControl } from "./event-control";
import { render as renderIntegration } from "./integration";
import { render as renderGroupLatentSpace } from "./group-latent-space";
import { render as renderLensBySource } from "./lens-by-source";
import { render as renderLensCorrelations } from "./lens-correlations";
import { render as renderLensExplorer } from "./lens-explorer";
import { render as renderLensMatrix } from "./lens-matrix";
import { render as renderLensPca } from "./lens-pca";
import { render as renderLensStability } from "./lens-stability";
import { render as renderLenses } from "./lenses";
import { render as renderRawJson } from "./raw-json";
import { render as renderScoreLab } from "./score-lab";
import { render as renderScraped } from "./scraped";
import { render as renderSnapshotCompare } from "./snapshot-compare";
import { render as renderSourceDifferentiation } from "./source-differentiation";
import { render as renderSourceEffects } from "./source-effects";
import { render as renderSourceTagMatrix } from "./source-tag-matrix";
import { render as renderSources } from "./sources";
import { render as renderStats } from "./stats";
import { render as renderTags } from "./tags";
import { render as renderTrends } from "./trends";
import { render as renderWorkflowStatus } from "./workflow-status";

const RENDERERS = {
  "data-quality": renderDataQuality,
  digest: renderDigest,
  "event-control": renderEventControl,
  "group-latent-space": renderGroupLatentSpace,
  integration: renderIntegration,
  "lens-by-source": renderLensBySource,
  "lens-correlations": renderLensCorrelations,
  "lens-explorer": renderLensExplorer,
  "lens-matrix": renderLensMatrix,
  "lens-pca": renderLensPca,
  "lens-stability": renderLensStability,
  lenses: renderLenses,
  "raw-json": renderRawJson,
  "score-lab": renderScoreLab,
  scraped: renderScraped,
  "snapshot-compare": renderSnapshotCompare,
  "source-differentiation": renderSourceDifferentiation,
  "source-effects": renderSourceEffects,
  "source-tag-matrix": renderSourceTagMatrix,
  sources: renderSources,
  stats: renderStats,
  tags: renderTags,
  trends: renderTrends,
  "workflow-status": renderWorkflowStatus
};

export async function renderNewsPageBody(slug, searchParams) {
  const renderer = RENDERERS[slug];
  if (!renderer) {
    return null;
  }
  return renderer(searchParams);
}
