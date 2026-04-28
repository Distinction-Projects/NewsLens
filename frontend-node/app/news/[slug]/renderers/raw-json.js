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
  const endpoint = getQueryParam(searchParams, "endpoint") || "digest";
  const dateFilter = getQueryParam(searchParams, "date");
  const tagFilter = getQueryParam(searchParams, "tag");
  const sourceFilter = getQueryParam(searchParams, "source");
  const limit = queryLimit(searchParams, "limit", 20, 1, 500);
  const forceRefresh = isTruthyQueryValue(getQueryParam(searchParams, "refresh"));

  let endpointPath = "/api/news/digest";
  if (endpoint === "latest") {
    endpointPath = "/api/news/digest/latest";
  } else if (endpoint === "stats") {
    endpointPath = "/api/news/stats";
  } else if (endpoint === "upstream") {
    endpointPath = "/api/news/upstream";
  } else if (endpoint === "freshness") {
    endpointPath = "/health/news-freshness";
  }

  const query = new URLSearchParams();
  if (snapshotDate) {
    query.set("snapshot_date", snapshotDate);
  }
  if (forceRefresh) {
    query.set("refresh", "true");
  }
  if (endpoint === "digest" || endpoint === "latest") {
    if (dateFilter) {
      query.set("date", dateFilter);
    }
    if (tagFilter) {
      query.set("tag", tagFilter);
    }
    if (sourceFilter) {
      query.set("source", sourceFilter);
    }
  }
  if (endpoint === "digest") {
    query.set("limit", String(limit));
  }

  const fullPath = `${endpointPath}${query.toString() ? `?${query.toString()}` : ""}`;
  const payloadStatus = await fetchEndpointStatus(
    "Selected endpoint",
    fullPath,
    forceRefresh ? { fetchOptions: { cache: "no-store" } } : {}
  );
  const payload = payloadStatus.payload;
  const json = JSON.stringify(payload || { error: payloadStatus.detail }, null, 2);
  const maxLength = 20000;
  const preview = json.length > maxLength ? `${json.slice(0, maxLength)}\n... truncated ...` : json;
  const payloadMeta = asObject(asObject(payload).meta);
  const generatedAt = payloadMeta.generated_at || "n/a";
  const applyHref = buildQueryHref({
    endpoint,
    date: dateFilter,
    tag: tagFilter,
    source: sourceFilter,
    limit: endpoint === "digest" ? String(limit) : "",
    data_mode: dataMode,
    snapshot: dataMode === "snapshot" ? selectedSnapshotDateValue(searchParams) : "",
    refresh: ""
  });
  const refreshHref = buildQueryHref({
    endpoint,
    date: dateFilter,
    tag: tagFilter,
    source: sourceFilter,
    limit: endpoint === "digest" ? String(limit) : "",
    data_mode: dataMode,
    snapshot: dataMode === "snapshot" ? selectedSnapshotDateValue(searchParams) : "",
    refresh: "1"
  });

  return (
    <>
      <DataModeControls
        searchParams={searchParams}
        extraParams={{
          endpoint,
          date: dateFilter,
          tag: tagFilter,
          source: sourceFilter,
          limit: String(limit)
        }}
      />
      <div className="panel">
        <h3>Raw Endpoint Controls</h3>
        <form method="get" className="news-filter-grid">
          <label className="muted">
            Endpoint
            <select name="endpoint" defaultValue={endpoint}>
              <option value="digest">Digest</option>
              <option value="latest">Latest Digest Item</option>
              <option value="stats">Stats</option>
              <option value="upstream">Upstream Contract (raw)</option>
              <option value="freshness">Freshness</option>
            </select>
          </label>
          <label className="muted">
            Date filter
            <input name="date" type="text" placeholder="YYYY-MM-DD" defaultValue={dateFilter} />
          </label>
          <label className="muted">
            Tag filter
            <input name="tag" type="text" placeholder="OpenAI" defaultValue={tagFilter} />
          </label>
          <label className="muted">
            Source filter
            <input name="source" type="text" placeholder="NPR" defaultValue={sourceFilter} />
          </label>
          <label className="muted">
            Limit
            <input name="limit" type="number" min="1" max="500" defaultValue={limit} />
          </label>
          <input type="hidden" name="data_mode" value={dataMode} />
          <input type="hidden" name="snapshot" value={selectedSnapshotDateValue(searchParams)} />
          <div style={{ display: "flex", alignItems: "end", gap: "10px" }}>
            <button type="submit" className="news-nav-link">
              Apply
            </button>
            <a className="news-nav-link" href={refreshHref}>
              Refresh
            </a>
          </div>
        </form>
        <p className="muted" style={{ marginTop: "10px" }}>
          <a href={applyHref}>Clear refresh flag</a>
        </p>
      </div>

      <div className="panel">
        <h3>Raw Endpoint Preview</h3>
        <p className="muted">
          Endpoint: <code>{fullPath}</code>
          <br />
          HTTP: <strong>{payloadStatus.statusCode || "n/a"}</strong> | Mode: <strong>{dataMode}</strong> | Generated:{" "}
          <strong>{generatedAt}</strong>
          {snapshotDate ? (
            <>
              {" "}
              for snapshot <code>{snapshotDate}</code>
            </>
          ) : null}
        </p>
        <pre className="json-preview">{preview}</pre>
      </div>
    </>
  );
}
