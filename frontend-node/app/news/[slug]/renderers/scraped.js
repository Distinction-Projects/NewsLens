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
  const sourceFilter = getQueryParam(searchParams, "source");
  const limit = queryLimit(searchParams, "limit", 100, 1, 500);
  const onlyScraped = getQueryParam(searchParams, "only") ? isTruthyQueryValue(getQueryParam(searchParams, "only")) : true;
  const forceRefresh = isTruthyQueryValue(getQueryParam(searchParams, "refresh"));

  const digestParams = new URLSearchParams();
  digestParams.set("limit", String(limit));
  if (sourceFilter) {
    digestParams.set("source", sourceFilter);
  }
  if (snapshotDate) {
    digestParams.set("snapshot_date", snapshotDate);
  }
  if (forceRefresh) {
    digestParams.set("refresh", "true");
  }

  const payload = await fetchNewsJson(`/api/news/digest?${digestParams.toString()}`, forceRefresh ? { cache: "no-store" } : {});
  const rows = asArray(payload?.data);
  const meta = asObject(payload?.meta);
  const hasScrapedPayload = (row) => {
    const scraped = asObject(row?.scraped);
    return Object.keys(scraped).length > 0;
  };
  const sourceNameForRow = (row) => row?.source_name || asObject(row?.source).name || asObject(row?.source).id || "Unknown source";
  const filteredRows = onlyScraped ? rows.filter((row) => hasScrapedPayload(row)) : rows;
  const grouped = new Map();
  for (const row of filteredRows) {
    const source = sourceNameForRow(row);
    if (!grouped.has(source)) {
      grouped.set(source, []);
    }
    grouped.get(source).push(row);
  }
  const groups = Array.from(grouped.entries()).sort((a, b) => String(a[0]).localeCompare(String(b[0])));
  const refreshHref = buildQueryHref({
    data_mode: dataMode,
    snapshot: dataMode === "snapshot" ? selectedSnapshotDateValue(searchParams) : "",
    source: sourceFilter,
    limit,
    only: onlyScraped ? "1" : "0",
    refresh: "1"
  });
  const generatedAt = String(meta?.generated_at || "n/a");
  const sourceMode = String(meta?.source_mode || "unknown");
  const withPayloadCount = rows.filter((row) => hasScrapedPayload(row)).length;
  const trailingStatus = onlyScraped ? "filtered to records with scraped payload" : "showing all records";

  return (
    <>
      <DataModeControls searchParams={searchParams} />
      <div className="panel">
        <h3>Scraped Filters</h3>
        <form method="get" className="inline-form-grid">
          <input type="hidden" name="data_mode" value={dataMode} />
          <input type="hidden" name="snapshot" value={selectedSnapshotDateValue(searchParams)} />
          <label className="muted" htmlFor="scraped-source-filter">
            Source
          </label>
          <input id="scraped-source-filter" name="source" type="text" placeholder="Fox, PBS, NPR..." defaultValue={sourceFilter} />
          <label className="muted" htmlFor="scraped-limit-filter">
            Limit
          </label>
          <input id="scraped-limit-filter" name="limit" type="number" min="1" max="500" defaultValue={String(limit)} />
          <label className="muted" htmlFor="scraped-only-filter">
            Records shown
          </label>
          <select id="scraped-only-filter" name="only" defaultValue={onlyScraped ? "1" : "0"}>
            <option value="1">Only with scraped payload</option>
            <option value="0">All records</option>
          </select>
          <div style={{ display: "flex", gap: "10px", alignItems: "center" }}>
            <button type="submit" className="news-nav-link active-link">
              Apply
            </button>
            <a className="news-nav-link" href={refreshHref}>
              Refresh
            </a>
          </div>
        </form>
      </div>
      <div className="panel">
        <h3>Status</h3>
        <p className="muted" style={{ marginTop: 0 }}>
          Records loaded: {formatNumber(rows.length)}; {trailingStatus}
        </p>
        <div className="stats-grid">
          <StatCard label="Records Loaded" value={formatNumber(rows.length)} />
          <StatCard label="Source Mode" value={sourceMode} />
          <StatCard label="Generated At (UTC)" value={generatedAt} />
          <StatCard label="Filter Applied" value={onlyScraped ? "scraped only" : "all records"} />
        </div>
      </div>
      <div className="panel">
        <h3>Raw Scraped Article Data</h3>
        <div className="stats-grid">
          <StatCard label="Records Shown" value={formatNumber(filteredRows.length)} />
          <StatCard label="Sources" value={formatNumber(groups.length)} />
          <StatCard label="With Scraped Payload" value={formatNumber(withPayloadCount)} />
        </div>
      </div>

      <div className="panel">
        <h3>Grouped by Source</h3>
        {groups.length === 0 ? (
          <p className="muted">No records match the current filters.</p>
        ) : (
          <div>
            {groups.slice(0, 25).map(([source, sourceRows]) => (
              <details key={source} className="news-page-intro" style={{ marginBottom: "10px" }}>
                <summary>
                  {source} ({formatNumber(sourceRows.length)} article{sourceRows.length === 1 ? "" : "s"})
                </summary>
                <div style={{ marginTop: "10px", display: "grid", gap: "10px" }}>
                  {sourceRows.map((row, index) => (
                    <div key={`${String(row?.id || row?.link || row?.title || "article")}-${index}`} className="panel">
                      <p style={{ marginTop: 0, marginBottom: "6px" }}>
                        <strong>{row?.title || "Untitled"}</strong>
                        <span className="muted" style={{ marginLeft: "8px", fontSize: "0.85em" }}>
                          [{String(row?.id || "no-id")}]
                        </span>
                      </p>
                      <p className="muted" style={{ marginTop: 0 }}>
                        Published: {String(row?.published_at || row?.published || "Unknown date")} | Has scraped:{" "}
                        {hasScrapedPayload(row) ? "yes" : "no"}
                      </p>
                      {row?.link ? (
                        <p style={{ marginTop: 0, marginBottom: "8px", display: "inline-block" }}>
                          <a className="news-nav-link" href={row.link} target="_blank" rel="noreferrer">
                            Open article
                          </a>
                        </p>
                      ) : (
                        <p className="muted" style={{ marginTop: 0, marginBottom: "8px" }}>
                          No link
                        </p>
                      )}
                      <pre className="json-preview">
                        {hasScrapedPayload(row) ? JSON.stringify(asObject(row?.scraped), null, 2) : "No scraped payload."}
                      </pre>
                    </div>
                  ))}
                </div>
              </details>
            ))}
          </div>
        )}
      </div>
    </>
  );
}
