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
  const dateFilter = getQueryParam(searchParams, "date");
  const tagFilter = getQueryParam(searchParams, "tag");
  const sourceFilter = getQueryParam(searchParams, "source");
  const limit = queryLimit(searchParams, "limit", 20, 1, 200);
  const forceRefresh = isTruthyQueryValue(getQueryParam(searchParams, "refresh"));

  const digestParams = new URLSearchParams();
  digestParams.set("limit", String(limit));
  if (dateFilter) {
    digestParams.set("date", dateFilter);
  }
  if (tagFilter) {
    digestParams.set("tag", tagFilter);
  }
  if (sourceFilter) {
    digestParams.set("source", sourceFilter);
  }
  if (snapshotDate) {
    digestParams.set("snapshot_date", snapshotDate);
  }
  if (forceRefresh) {
    digestParams.set("refresh", "true");
  }

  const latestParams = new URLSearchParams();
  if (dateFilter) {
    latestParams.set("date", dateFilter);
  }
  if (tagFilter) {
    latestParams.set("tag", tagFilter);
  }
  if (sourceFilter) {
    latestParams.set("source", sourceFilter);
  }
  if (snapshotDate) {
    latestParams.set("snapshot_date", snapshotDate);
  }
  if (forceRefresh) {
    latestParams.set("refresh", "true");
  }

  const [digestPayload, latestPayload] = await Promise.all([
    fetchNewsJson(`/api/news/digest?${digestParams.toString()}`, forceRefresh ? { cache: "no-store" } : {}),
    fetchNewsJson(
      `/api/news/digest/latest${latestParams.toString() ? `?${latestParams.toString()}` : ""}`,
      forceRefresh ? { cache: "no-store" } : {}
    )
  ]);
  const meta = asObject(digestPayload?.meta);
  const rows = Array.isArray(digestPayload?.data) ? digestPayload.data : [];
  const latest = asObject(latestPayload?.data);
  const sourceCounts = new Map();
  const avgBySource = new Map();
  for (const article of rows) {
    const source = String(article?.source_name || article?.source?.name || "Unknown");
    sourceCounts.set(source, (sourceCounts.get(source) || 0) + 1);
    const scorePercent = toNumber(article?.score?.percent);
    if (scorePercent !== null) {
      const bucket = avgBySource.get(source) || { total: 0, n: 0 };
      bucket.total += scorePercent;
      bucket.n += 1;
      avgBySource.set(source, bucket);
    }
  }
  const topSources = Array.from(sourceCounts.entries())
    .sort((a, b) => b[1] - a[1])
    .slice(0, 12);
  const avgSourceScores = topSources
    .map(([source]) => {
      const bucket = avgBySource.get(source);
      const average = bucket && bucket.n > 0 ? bucket.total / bucket.n : null;
      return { source, average };
    })
    .filter((row) => row.average !== null);

  const refreshHref = buildQueryHref({
    data_mode: dataMode,
    snapshot: dataMode === "snapshot" ? selectedSnapshotDateValue(searchParams) : "",
    date: dateFilter,
    tag: tagFilter,
    source: sourceFilter,
    limit,
    refresh: "1"
  });
  const sourceMode = String(meta?.source_mode || "unknown");
  const generatedAt = String(meta?.generated_at || "n/a");
  const fromCache = isTruthyQueryValue(meta?.from_cache);
  const usingLastGood = isTruthyQueryValue(meta?.using_last_good);
  const latestTitle = String(latest?.title || "No matching article");
  const latestSource = String(latest?.source_name || asObject(latest?.source).name || "Unknown");
  const latestPublished = String(latest?.published_at || latest?.published || "Unknown");
  const latestSummary = String(latest?.ai_summary || latest?.summary || "No summary available.");
  const latestTags = asArray(latest?.tags);

  return (
    <>
      <DataModeControls searchParams={searchParams} />
      <div className="panel">
        <h3>Digest Filters</h3>
        <form method="get" className="inline-form-grid">
          <input type="hidden" name="data_mode" value={dataMode} />
          <input type="hidden" name="snapshot" value={selectedSnapshotDateValue(searchParams)} />
          <label className="muted" htmlFor="digest-date-filter">
            Date (UTC)
          </label>
          <input id="digest-date-filter" name="date" type="text" placeholder="YYYY-MM-DD" defaultValue={dateFilter} />
          <label className="muted" htmlFor="digest-tag-filter">
            Tag
          </label>
          <input id="digest-tag-filter" name="tag" type="text" placeholder="OpenAI" defaultValue={tagFilter} />
          <label className="muted" htmlFor="digest-source-filter">
            Source
          </label>
          <input id="digest-source-filter" name="source" type="text" placeholder="PBS" defaultValue={sourceFilter} />
          <label className="muted" htmlFor="digest-limit-filter">
            Limit
          </label>
          <input id="digest-limit-filter" name="limit" type="number" min="1" max="200" defaultValue={String(limit)} />
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
        <h3>Digest Status</h3>
        <div className="stats-grid">
          <StatCard label="Items Returned" value={formatNumber(meta?.returned_count ?? rows.length)} />
          <StatCard label="Generated At (UTC)" value={generatedAt} />
          <StatCard label="Source Mode" value={sourceMode} />
          <StatCard label="From Cache" value={fromCache ? "yes" : "no"} />
          <StatCard label="Using Last Good" value={usingLastGood ? "yes" : "no"} />
        </div>
      </div>
      <div className="panel">
        <h3>Latest Match</h3>
        <p className="muted" style={{ marginBottom: "8px" }}>
          {latestSource} • {latestPublished}
        </p>
        <h4 style={{ marginTop: 0 }}>{latestTitle}</h4>
        <p>{latestSummary}</p>
        {latestTags.length > 0 ? <p className="muted">Tags: {latestTags.join(", ")}</p> : null}
        {latest?.link ? (
          <a className="news-nav-link" href={latest.link} target="_blank" rel="noreferrer">
            Open article
          </a>
        ) : null}
      </div>
      <div className="panel">
        <h3>Digest Visuals</h3>
        {rows.length === 0 ? (
          <EmptyState />
        ) : (
          <div className="chart-grid">
            <PlotlyChart
              data={[
                {
                  type: "bar",
                  x: topSources.map((row) => row[0]),
                  y: topSources.map((row) => row[1]),
                  marker: { color: "#4fd1c5" }
                }
              ]}
              layout={{ title: "Top Sources in Current Digest Window", yaxis: { title: "Articles" } }}
            />
            <PlotlyChart
              data={[
                {
                  type: "bar",
                  x: avgSourceScores.map((row) => row.source),
                  y: avgSourceScores.map((row) => row.average),
                  marker: { color: "#7aa7ff" }
                }
              ]}
              layout={{ title: "Average Score % by Source (Scored Rows)", yaxis: { title: "Score %" } }}
            />
          </div>
        )}
      </div>
      <div className="panel">
        <h3>Latest Articles ({rows.length})</h3>
        {rows.length === 0 ? (
          <p className="muted">No articles available.</p>
        ) : (
          <table className="news-table">
            <thead>
              <tr>
                <th>Date</th>
                <th>Source</th>
                <th>Title</th>
                <th>Tags</th>
                <th>Score %</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((article) => (
                <tr key={article.id || article.link}>
                  <td>{article.published_at || "n/a"}</td>
                  <td>{article.source_name || article?.source?.name || "Unknown"}</td>
                  <td>
                    <a href={article.link} target="_blank" rel="noreferrer">
                      {article.title || "Untitled"}
                    </a>
                  </td>
                  <td>{Array.isArray(article.tags) ? article.tags.join(", ") : "n/a"}</td>
                  <td>{typeof article?.score?.percent === "number" ? `${article.score.percent.toFixed(1)}%` : "n/a"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </>
  );
}
