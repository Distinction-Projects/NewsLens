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
  const derived = getStatsDerived(payload);
  const chartAggregates = asObject(derived.chart_aggregates);
  const scoreStatus = asObject(derived.score_status);
  const scoreStatusBySource = asArray(chartAggregates.score_status_by_source).slice(0, 20);
  const scoredBySource = asArray(chartAggregates.scored_by_source).slice(0, 20);
  const tagDistribution = asArray(chartAggregates.tag_count_distribution);
  const scoreStatusRows = scoreStatusBySource
    .map((row) => ({
      source: String(row?.source || "Unknown"),
      scored: toNumber(row?.scored) || 0,
      zero: toNumber(row?.zero_score) || 0,
      unscorable: toNumber(row?.unscorable) || 0
    }))
    .slice(0, 15);

  return (
    <>
      <DataModeControls searchParams={searchParams} />
      <div className="panel">
        <h3>Score Diagnostics</h3>
        <div className="stats-grid">
          <StatCard label="Scored Articles" value={formatNumber(derived.scored_articles)} />
          <StatCard label="Zero Scores" value={formatNumber(derived.zero_score_articles)} />
          <StatCard label="Unscorable" value={formatNumber(derived.unscorable_articles)} />
          <StatCard label="Missing Score Objects" value={formatNumber(derived.score_object_missing_articles)} />
          <StatCard label="Score Coverage" value={formatPercent(derived.score_coverage_ratio)} />
        </div>
      </div>

      <div className="panel">
        <h3>Score Lab Visuals</h3>
        {scoreStatusRows.length === 0 && scoredBySource.length === 0 && tagDistribution.length === 0 ? (
          <EmptyState />
        ) : (
          <div className="chart-grid">
            <PlotlyChart
              data={[
                {
                  type: "bar",
                  name: "Scored",
                  x: scoreStatusRows.map((row) => row.source),
                  y: scoreStatusRows.map((row) => row.scored),
                  marker: { color: "#4fd1c5" }
                },
                {
                  type: "bar",
                  name: "Zero",
                  x: scoreStatusRows.map((row) => row.source),
                  y: scoreStatusRows.map((row) => row.zero),
                  marker: { color: "#fd7e14" }
                },
                {
                  type: "bar",
                  name: "Unscorable",
                  x: scoreStatusRows.map((row) => row.source),
                  y: scoreStatusRows.map((row) => row.unscorable),
                  marker: { color: "#7aa7ff" }
                }
              ]}
              layout={{ title: "Score Status by Source", barmode: "group", yaxis: { title: "Articles" } }}
            />
            <PlotlyChart
              data={[
                {
                  type: "bar",
                  x: scoredBySource.map((row) => String(row?.source || "Unknown")),
                  y: scoredBySource.map((row) => toNumber(row?.count) || 0),
                  marker: { color: "#9d7dff" }
                }
              ]}
              layout={{ title: "Scored Articles by Source", yaxis: { title: "Articles" } }}
            />
            <PlotlyChart
              data={[
                {
                  type: "bar",
                  x: tagDistribution.map((row) => String(row?.label || "Unknown")),
                  y: tagDistribution.map((row) => toNumber(row?.count) || 0),
                  marker: { color: "#7aa7ff" }
                }
              ]}
              layout={{ title: "Tag Count Distribution", yaxis: { title: "Articles" } }}
            />
          </div>
        )}
      </div>

      <div className="panel">
        <h3>Score Status by Source</h3>
        {scoreStatusBySource.length === 0 ? (
          <EmptyState />
        ) : (
          <table className="news-table compact">
            <thead>
              <tr>
                <th>Source</th>
                <th>Scored</th>
                <th>Zero</th>
                <th>Unscorable</th>
              </tr>
            </thead>
            <tbody>
              {scoreStatusBySource.map((row) => (
                <tr key={String(row.source || "unknown")}>
                  <td>{row.source || "Unknown"}</td>
                  <td>{formatNumber(row.scored)}</td>
                  <td>{formatNumber(row.zero_score)}</td>
                  <td>{formatNumber(row.unscorable)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      <div className="panel">
        <h3>Scored Articles by Source</h3>
        {scoredBySource.length === 0 ? (
          <EmptyState />
        ) : (
          <table className="news-table compact">
            <thead>
              <tr>
                <th>Source</th>
                <th>Count</th>
              </tr>
            </thead>
            <tbody>
              {scoredBySource.map((row) => (
                <tr key={String(row.source || "unknown")}>
                  <td>{row.source || "Unknown"}</td>
                  <td>{formatNumber(row.count)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      <div className="panel">
        <h3>Tag Count Distribution</h3>
        {tagDistribution.length === 0 ? (
          <EmptyState />
        ) : (
          <table className="news-table compact">
            <thead>
              <tr>
                <th>Bucket</th>
                <th>Articles</th>
              </tr>
            </thead>
            <tbody>
              {tagDistribution.map((row) => (
                <tr key={String(row.label)}>
                  <td>{row.label}</td>
                  <td>{formatNumber(row.count)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
        <p className="muted">
          Scored: {formatNumber(scoreStatus.scored)} | Positive: {formatNumber(scoreStatus.positive)} | Zero:{" "}
          {formatNumber(scoreStatus.zero)}
        </p>
      </div>
    </>
  );
}
