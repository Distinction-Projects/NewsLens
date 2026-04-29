import { fetchNewsJson, newsApiBaseUrl } from "../../../../lib/newsApi";
import {
  activeSnapshotDate,
  asArray,
  asObject,
  buildQueryHref,
  fetchStatsForMode,
  formatAlreadyPercent,
  formatDecimal,
  formatNumber,
  formatPercent,
  getQueryParam,
  getStatsDerived,
  isTruthyQueryValue,
  normalizeDataMode,
  queryLimit,
  selectedSnapshotDateValue,
  snapshotDateFromSearchParams,
  toNumber,
  truncateText
} from "../../../../lib/newsPageUtils";
import PlotlyChart from "../../../../components/PlotlyChart";
import {
  DataModeControls,
  EmptyState,
  MiniBar,
  StatCard,
  StatusBlock,
  StatusPill
} from "../../../../components/news/NewsDashboardPrimitives";
import {
  EndpointTable,
  extractSnapshotMetrics,
  fetchEndpointStatus,
  getCorrelationPairRows,
  metricDelta,
  pairKey
} from "./shared";

export async function render(searchParams) {
  const payload = await fetchStatsForMode(searchParams);
  const data = payload?.data || {};
  const derived = data?.derived || {};
  const meta = payload?.meta || {};
  const summary = data?.summary || {};
  const scoreStatus = derived?.score_status || {};
  const sourceCounts = asArray(derived.source_counts).slice(0, 15);
  const tagCounts = asArray(derived.tag_counts).slice(0, 15);
  const dailyCounts = asArray(derived.daily_counts_utc);
  const sourceTopicControl = asObject(derived.source_topic_control);
  const tagSlicedAnalysis = asObject(derived.tag_sliced_analysis);
  const eventControl = asObject(derived.event_control);
  const driftDiagnostics = asObject(derived.drift_diagnostics);
  const latentStability = asObject(derived.latent_space_stability);
  const sourceReliability = asObject(derived.source_reliability);
  const sourceReliabilityPooled = asObject(sourceReliability.pooled);
  const sourceReliabilityEventControlled = asObject(sourceReliability.event_controlled);
  const sourceReliabilityMetrics = asObject(sourceReliabilityPooled.metrics);
  const sourceReliabilitySummary = asObject(sourceReliability.summary);
  const eventSummary = asObject(eventControl.summary);
  const eventCache = asObject(eventControl.cache);
  const driftSummary = asObject(driftDiagnostics.summary);
  const latentSummary = asObject(latentStability.summary);
  const topicSummary = asObject(sourceTopicControl.summary);
  const tagSliceSummary = asObject(tagSlicedAnalysis.summary);
  const analysisStatusRows = [
    { label: "Source differentiation", status: derived.source_differentiation?.status, reason: derived.source_differentiation?.reason },
    { label: "Source lens effects", status: derived.source_lens_effects?.status, reason: derived.source_lens_effects?.reason },
    { label: "Topic-controlled slices", status: topicSummary.analyzed_topic_count ? "ok" : "unavailable", reason: "" },
    { label: "Tag-controlled slices", status: tagSliceSummary.analyzed_tag_count ? "ok" : "unavailable", reason: "" },
    { label: "Event-controlled analysis", status: eventControl.status, reason: eventControl.reason || eventSummary.unavailable_reason },
    { label: "Drift diagnostics", status: driftDiagnostics.status, reason: driftDiagnostics.reason },
    { label: "Lens PCA", status: derived.lens_pca?.status, reason: derived.lens_pca?.reason },
    { label: "Lens MDS", status: derived.lens_mds?.status, reason: derived.lens_mds?.reason },
    { label: "Latent space stability", status: latentStability.status, reason: latentStability.reason },
    { label: "Lens time series", status: derived.lens_time_series?.status, reason: derived.lens_time_series?.reason }
  ];
  const statusRows = [
    { label: "Scored", value: toNumber(scoreStatus.scored) || 0 },
    { label: "Positive", value: toNumber(scoreStatus.positive) || 0 },
    { label: "Zero", value: toNumber(scoreStatus.zero) || 0 },
    { label: "Unscorable", value: toNumber(scoreStatus.unscorable) || 0 }
  ];

  return (
    <>
      <DataModeControls searchParams={searchParams} />
      <div className="panel">
        <h3>Coverage Snapshot</h3>
        <p className="muted">
          Source mode: <code>{meta.source_mode || "unknown"}</code>
        </p>
        <div className="stats-grid">
          <div className="stat-card">
            <span className="muted">Total Articles</span>
            <strong>{formatNumber(derived.total_articles ?? summary.articles)}</strong>
          </div>
          <div className="stat-card">
            <span className="muted">Scored Articles</span>
            <strong>{formatNumber(derived.scored_articles ?? summary.scored_articles)}</strong>
          </div>
          <div className="stat-card">
            <span className="muted">Coverage</span>
            <strong>{formatPercent(derived.score_coverage_ratio)}</strong>
          </div>
          <div className="stat-card">
            <span className="muted">Sources</span>
            <strong>{formatNumber(Array.isArray(derived.source_counts) ? derived.source_counts.length : 0)}</strong>
          </div>
        </div>
      </div>

      <div className="panel">
        <h3>Analysis Readiness</h3>
        <p className="muted">
          Shows which backend-derived analysis layers are available in this stats payload. Pooled source views remain
          topic-confounded; topic, tag, and event controls provide stricter comparison contexts.
        </p>
        <div className="stats-grid">
          <StatCard label="Stats Backend" value={meta.stats_backend || "dynamic"} />
          <StatCard label="Topic Slices" value={`${formatNumber(topicSummary.analyzed_topic_count)} / ${formatNumber(topicSummary.topic_count)}`} />
          <StatCard label="Tag Slices" value={`${formatNumber(tagSliceSummary.analyzed_tag_count)} / ${formatNumber(tagSliceSummary.shown_tag_count || tagSliceSummary.tag_count)}`} />
          <StatCard label="Events" value={formatNumber(eventSummary.event_count)} />
          <StatCard label="Multi-Source Events" value={formatNumber(eventSummary.multi_source_event_count)} />
          <StatCard label="Event Embeddings" value={formatNumber(eventSummary.embedded_count)} />
          <StatCard label="Embedding Cache" value={`${formatNumber(eventCache.hits)} hits / ${formatNumber(eventCache.stored)} stored`} />
          <StatCard label="Drift Severity" value={driftSummary.severity || "n/a"} />
          <StatCard label="Drift Score" value={formatDecimal(driftSummary.drift_score, 3)} />
          <StatCard label="Stable PCA Components" value={`${formatNumber(latentSummary.stable_component_count)} / ${formatNumber(latentSummary.component_count)}`} />
          <StatCard label="Reliability Tier" value={sourceReliabilityPooled.tier || "n/a"} />
          <StatCard label="Event-Control Reliability" value={sourceReliabilityEventControlled.tier || "n/a"} />
          <StatCard label="Reliable Tag Slices" value={`${formatNumber(sourceReliabilitySummary.ok_tag_count)} / ${formatNumber(sourceReliabilitySummary.tag_count)}`} />
        </div>
        <div className="chart-grid">
          <PlotlyChart
            data={[
              {
                type: "bar",
                x: ["Topics analyzed", "Topics unavailable", "Tags analyzed", "Tags unavailable", "Events", "Multi-source events"],
                y: [
                  toNumber(topicSummary.analyzed_topic_count) || 0,
                  toNumber(topicSummary.unavailable_topic_count) || 0,
                  toNumber(tagSliceSummary.analyzed_tag_count) || 0,
                  toNumber(tagSliceSummary.unavailable_tag_count) || 0,
                  toNumber(eventSummary.event_count) || 0,
                  toNumber(eventSummary.multi_source_event_count) || 0
                ],
                marker: { color: ["#4fd1c5", "#ffcc66", "#7aa7ff", "#ffcc66", "#fd7e14", "#9d7dff"] }
              }
            ]}
            layout={{ title: "Controlled Analysis Coverage", yaxis: { title: "Count" } }}
          />
          <PlotlyChart
            data={[
              {
                type: "bar",
                x: ["Accuracy", "Baseline", "Lift", "Best q-value"],
                y: [
                  toNumber(sourceReliabilityMetrics.classification_accuracy) || 0,
                  toNumber(sourceReliabilityMetrics.classification_baseline_accuracy) || 0,
                  toNumber(sourceReliabilityMetrics.classification_lift) || 0,
                  toNumber(sourceReliabilityMetrics.best_q_value) || 0
                ],
                marker: { color: "#4fd1c5" }
              }
            ]}
            layout={{ title: "Pooled Source Reliability Signals", yaxis: { title: "Value" } }}
          />
        </div>
        <table className="news-table compact">
          <thead>
            <tr>
              <th>Layer</th>
              <th>Status</th>
              <th>Reason</th>
            </tr>
          </thead>
          <tbody>
            {analysisStatusRows.map((row) => (
              <tr key={row.label}>
                <td>{row.label}</td>
                <td>
                  <StatusPill status={String(row.status || "unavailable")} />
                </td>
                <td>{row.reason || ""}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="panel">
        <h3>Score Status</h3>
        <div className="chart-grid">
          <PlotlyChart
            data={[
              {
                type: "bar",
                x: sourceCounts.map((row) => String(row.source || "Unknown")),
                y: sourceCounts.map((row) => toNumber(row.count) || 0),
                marker: { color: "#4fd1c5" }
              }
            ]}
            layout={{ title: "Article Volume by Source", yaxis: { title: "Articles" } }}
          />
          <PlotlyChart
            data={[
              {
                type: "bar",
                x: tagCounts.map((row) => String(row.tag || "Unknown")),
                y: tagCounts.map((row) => toNumber(row.count) || 0),
                marker: { color: "#fd7e14" }
              }
            ]}
            layout={{ title: "Top Tags", yaxis: { title: "Count" } }}
          />
          <PlotlyChart
            data={[
              {
                type: "bar",
                x: statusRows.map((row) => row.label),
                y: statusRows.map((row) => row.value),
                marker: { color: "#7aa7ff" }
              }
            ]}
            layout={{ title: "Score Status Counts", yaxis: { title: "Articles" } }}
          />
          <PlotlyChart
            data={[
              {
                type: "scatter",
                mode: "lines+markers",
                x: dailyCounts.map((row) => String(row.date || "")),
                y: dailyCounts.map((row) => toNumber(row.count) || 0),
                line: { color: "#9d7dff" }
              }
            ]}
            layout={{ title: "Daily Articles (UTC)", yaxis: { title: "Articles" } }}
          />
        </div>
        <table className="news-table compact">
          <tbody>
            <tr>
              <th>Scored</th>
              <td>{formatNumber(scoreStatus.scored)}</td>
            </tr>
            <tr>
              <th>Positive</th>
              <td>{formatNumber(scoreStatus.positive)}</td>
            </tr>
            <tr>
              <th>Zero</th>
              <td>{formatNumber(scoreStatus.zero)}</td>
            </tr>
            <tr>
              <th>Unscorable</th>
              <td>{formatNumber(scoreStatus.unscorable)}</td>
            </tr>
          </tbody>
        </table>
      </div>
    </>
  );
}
