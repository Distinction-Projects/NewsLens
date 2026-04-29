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
  const dataMode = normalizeDataMode(searchParams);
  const snapshotDate = activeSnapshotDate(searchParams);
  const forceRefresh = isTruthyQueryValue(getQueryParam(searchParams, "refresh"));
  const requestOptions = forceRefresh ? { fetchOptions: { cache: "no-store" } } : {};

  const digestParams = new URLSearchParams();
  digestParams.set("limit", "5");
  if (snapshotDate) {
    digestParams.set("snapshot_date", snapshotDate);
  }
  if (forceRefresh) {
    digestParams.set("refresh", "true");
  }

  const latestParams = new URLSearchParams();
  if (snapshotDate) {
    latestParams.set("snapshot_date", snapshotDate);
  }
  if (forceRefresh) {
    latestParams.set("refresh", "true");
  }

  const statsParams = new URLSearchParams();
  if (snapshotDate) {
    statsParams.set("snapshot_date", snapshotDate);
  }
  if (forceRefresh) {
    statsParams.set("refresh", "true");
  }

  const rows = await Promise.all([
    fetchEndpointStatus("Digest endpoint reachable", `/api/news/digest?${digestParams.toString()}`, requestOptions),
    fetchEndpointStatus(
      "Latest endpoint reachable",
      `/api/news/digest/latest${latestParams.toString() ? `?${latestParams.toString()}` : ""}`,
      requestOptions
    ),
    fetchEndpointStatus(
      "Stats endpoint reachable",
      `/api/news/stats${statsParams.toString() ? `?${statsParams.toString()}` : ""}`,
      requestOptions
    ),
    fetchEndpointStatus("Freshness endpoint reachable", "/health/news-freshness", requestOptions)
  ]);
  const digestRow = rows[0];
  const latestRow = rows[1];
  const freshnessRow = rows[3];

  const digestMeta = asObject(digestRow?.payload?.meta);
  const statsPayload = asObject(rows[2]?.payload);
  const statsData = asObject(statsPayload.data);
  const statsDerived = asObject(statsData.derived);
  const upstreamSummary = asObject(statsDerived.upstream_summary);
  const upstreamAnalysis = asObject(statsDerived.upstream_analysis);
  const upstreamLensSummary = asObject(upstreamAnalysis.lens_summary);
  const upstreamLensRows = asArray(upstreamLensSummary.lenses);
  const upstreamSourceDifferentiation = asObject(upstreamAnalysis.source_differentiation);
  const upstreamClassification = asObject(upstreamSourceDifferentiation.classification);
  const upstreamMultivariate = asObject(upstreamSourceDifferentiation.multivariate);
  const digestItems = asArray(digestRow?.payload?.data);
  const latestRecord = asObject(latestRow?.payload?.data);
  const freshnessPayload = asObject(freshnessRow?.payload);
  const generatedAt = String(digestMeta?.generated_at || "missing");
  const hasGeneratedAt = generatedAt !== "missing";
  const hasArticles = digestItems.length > 0;
  const freshnessReachable = freshnessRow?.ok || false;
  const freshnessIsFresh = Boolean(freshnessPayload?.is_fresh);
  const integrationOk = Boolean(digestRow?.ok) && Boolean(rows[2]?.ok) && freshnessReachable && hasGeneratedAt;
  const staleWarning = freshnessReachable && !freshnessIsFresh;
  const refreshHref = buildQueryHref({
    data_mode: dataMode,
    snapshot: dataMode === "snapshot" ? selectedSnapshotDateValue(searchParams) : "",
    refresh: "1"
  });
  const checkRows = [
    ...rows,
    {
      label: "Payload includes generated_at",
      path: "digest.meta.generated_at",
      ok: hasGeneratedAt,
      status: hasGeneratedAt ? "ok" : "missing",
      detail: `generated_at=${generatedAt}`
    },
    {
      label: "Payload has articles",
      path: "digest.data",
      ok: hasArticles,
      status: hasArticles ? "ok" : "empty",
      detail: `items=${digestItems.length}`
    }
  ];
  const debugPayload = {
    digest_status_code: digestRow?.ok ? 200 : null,
    latest_status_code: latestRow?.ok ? 200 : null,
    stats_status_code: rows[2]?.ok ? 200 : null,
    freshness_status_code: freshnessRow?.ok ? 200 : null,
    digest_status: digestRow?.payload?.status || null,
    latest_status: latestRow?.payload?.status || null,
    stats_status: rows[2]?.payload?.status || null,
    freshness_status: freshnessPayload?.status || null,
    from_cache: digestMeta?.from_cache,
    using_last_good: digestMeta?.using_last_good,
    fetch_error: digestMeta?.fetch_error,
    freshness_reason: freshnessPayload?.reason || null
  };
  const healthy = rows.filter((row) => row.ok).length;

  return (
    <>
      <DataModeControls searchParams={searchParams} />
      <div className="panel">
        <h3>Refresh</h3>
        <a className="news-nav-link" href={refreshHref}>
          Refresh checks
        </a>
      </div>
      <div className="panel">
        <h3>Integration Banner</h3>
        {integrationOk && !staleWarning ? (
          <StatusPill tone="good">Integration checks passing. Data is fresh.</StatusPill>
        ) : integrationOk && staleWarning ? (
          <StatusPill tone="neutral">Integration passing, but freshness is stale.</StatusPill>
        ) : (
          <StatusPill tone="bad">Integration check failure. Review endpoint statuses.</StatusPill>
        )}
      </div>
      <div className="panel">
        <h3>Integration Summary</h3>
        <div className="stats-grid">
          <StatCard label="Checks Passing" value={`${formatNumber(healthy)} / ${formatNumber(rows.length)}`} />
          <StatCard label="Generated At" value={generatedAt} />
          <StatCard label="Digest Items" value={formatNumber(digestItems.length)} />
          <StatCard label="Latest Title" value={truncateText(latestRecord?.title || "unavailable", 72)} />
          <StatCard label="Freshness Status" value={freshnessIsFresh ? "fresh" : "stale"} />
        </div>
      </div>

      <div className="panel">
        <h3>Upstream Analysis Contract</h3>
        <p className="muted">
          Confirms that the upstream RSS/scoring bundle contains enough lens and source-analysis material for the dashboard
          contract, independent of page-level rendering.
        </p>
        <div className="stats-grid">
          <StatCard label="Upstream Articles" value={formatNumber(upstreamSummary.articles)} />
          <StatCard label="Digest Articles" value={formatNumber(upstreamSummary.digest_articles)} />
          <StatCard label="History Added" value={formatNumber(upstreamSummary.history_articles_added)} />
          <StatCard label="Scored Articles" value={formatNumber(upstreamSummary.scored_articles)} />
          <StatCard label="Lens-Scored Articles" value={formatNumber(upstreamSummary.lens_scored_articles)} />
          <StatCard label="Upstream Lenses" value={formatNumber(upstreamLensRows.length)} />
          <StatCard label="Upstream Sources" value={formatNumber(upstreamSourceDifferentiation.n_sources)} />
          <StatCard label="Upstream LOOCV Accuracy" value={formatPercent(upstreamClassification.accuracy)} />
        </div>
        <div className="chart-grid">
          <PlotlyChart
            data={[
              {
                type: "bar",
                x: upstreamLensRows.map((row) => String(row.name || "Unknown")),
                y: upstreamLensRows.map((row) => toNumber(row.items_with_scores) || 0),
                marker: { color: "#4fd1c5" }
              }
            ]}
            layout={{ title: "Upstream Lens Score Coverage", yaxis: { title: "Items with scores" } }}
          />
          <table className="news-table compact">
            <tbody>
              <tr>
                <th>Source differentiation status</th>
                <td>{String(upstreamSourceDifferentiation.status || "unavailable")}</td>
              </tr>
              <tr>
                <th>Articles in source analysis</th>
                <td>{formatNumber(upstreamSourceDifferentiation.n_articles)}</td>
              </tr>
              <tr>
                <th>Multivariate F</th>
                <td>{formatDecimal(upstreamMultivariate.f_stat, 4)}</td>
              </tr>
              <tr>
                <th>Multivariate p_perm</th>
                <td>{formatDecimal(upstreamMultivariate.p_perm, 4)}</td>
              </tr>
              <tr>
                <th>Classifier baseline</th>
                <td>{formatPercent(upstreamClassification.baseline_accuracy)}</td>
              </tr>
            </tbody>
          </table>
        </div>
        {upstreamLensRows.length === 0 ? (
          <EmptyState>No upstream lens summary rows available.</EmptyState>
        ) : (
          <table className="news-table compact">
            <thead>
              <tr>
                <th>Lens</th>
                <th>Rubrics</th>
                <th>Max Total</th>
                <th>Items With Scores</th>
              </tr>
            </thead>
            <tbody>
              {upstreamLensRows.map((row) => (
                <tr key={String(row.name || "unknown-lens")}>
                  <td>{row.name || "Unknown"}</td>
                  <td>{formatNumber(row.rubric_count)}</td>
                  <td>{formatDecimal(row.max_total, 1)}</td>
                  <td>{formatNumber(row.items_with_scores)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      <div className="panel">
        <h3>Contract Checks</h3>
        <EndpointTable rows={checkRows} />
      </div>

      <div className="panel">
        <h3>Debug Payload</h3>
        <pre className="json-preview">{JSON.stringify(debugPayload, null, 2)}</pre>
      </div>
    </>
  );
}
