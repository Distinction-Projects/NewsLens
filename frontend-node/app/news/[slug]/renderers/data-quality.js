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
  const dataQuality = asObject(derived.data_quality);
  const summary = asObject(dataQuality.summary);
  const scoreStatus = asObject(derived.score_status);
  const fieldCoverage = asArray(dataQuality.field_coverage);

  return (
    <>
      <DataModeControls searchParams={searchParams} />
      <div className="panel">
        <h3>Quality Snapshot</h3>
        <div className="stats-grid">
          <StatCard label="Included Articles" value={formatNumber(summary.total ?? derived.total_articles)} />
          <StatCard label="Input Articles" value={formatNumber(derived.input_articles)} />
          <StatCard label="Excluded Unscraped" value={formatNumber(derived.excluded_unscraped_articles)} />
          <StatCard label="Scored" value={formatNumber(summary.scored ?? derived.scored_articles)} />
          <StatCard label="Unscorable" value={formatNumber(scoreStatus.unscorable ?? derived.unscorable_articles)} />
          <StatCard label="Avg Tags / Article" value={formatDecimal(summary.average_tags, 2)} />
        </div>
      </div>

      <div className="panel">
        <h3>Field Coverage</h3>
        {fieldCoverage.length === 0 ? (
          <EmptyState />
        ) : (
          <table className="news-table">
            <thead>
              <tr>
                <th>Field</th>
                <th>Present</th>
                <th>Missing</th>
                <th>Coverage</th>
              </tr>
            </thead>
            <tbody>
              {fieldCoverage.map((row) => (
                <tr key={String(row.field)}>
                  <td>{row.field}</td>
                  <td>{formatNumber(row.present)}</td>
                  <td>{formatNumber(row.missing)}</td>
                  <td>
                    {formatAlreadyPercent(row.coverage_percent)}
                    <MiniBar value={row.coverage_percent} max={100} />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      <div className="panel">
        <h3>Known Issue Counts</h3>
        <table className="news-table compact">
          <tbody>
            <tr>
              <th>Missing AI Summary</th>
              <td>{formatNumber(summary.missing_ai_summary)}</td>
            </tr>
            <tr>
              <th>Missing Published Date</th>
              <td>{formatNumber(summary.missing_published)}</td>
            </tr>
            <tr>
              <th>Missing Source</th>
              <td>{formatNumber(summary.missing_source)}</td>
            </tr>
            <tr>
              <th>Placeholder Zero Unscorable</th>
              <td>{formatNumber(scoreStatus.placeholder_zero_unscorable)}</td>
            </tr>
          </tbody>
        </table>
      </div>
    </>
  );
}
