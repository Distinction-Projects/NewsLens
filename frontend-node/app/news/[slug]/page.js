import { notFound } from "next/navigation";
import { fetchNewsJson, newsApiBaseUrl } from "../../../lib/newsApi";
import { getNewsPage, NEWS_PAGES } from "../../../lib/newsPages";
import PlotlyChart from "../../../components/PlotlyChart";

export const dynamic = "force-dynamic";

function asArray(value) {
  return Array.isArray(value) ? value : [];
}

function asObject(value) {
  return value && typeof value === "object" && !Array.isArray(value) ? value : {};
}

function toNumber(value) {
  const number = typeof value === "number" ? value : Number(value);
  return Number.isFinite(number) ? number : null;
}

function formatNumber(value) {
  const number = toNumber(value);
  if (number === null) {
    return "n/a";
  }
  return new Intl.NumberFormat("en-US").format(number);
}

function formatDecimal(value, digits = 2) {
  const number = toNumber(value);
  if (number === null) {
    return "n/a";
  }
  return number.toFixed(digits);
}

function formatPercent(value) {
  const number = toNumber(value);
  if (number === null) {
    return "n/a";
  }
  return `${(number * 100).toFixed(1)}%`;
}

function formatAlreadyPercent(value) {
  const number = toNumber(value);
  if (number === null) {
    return "n/a";
  }
  return `${number.toFixed(1)}%`;
}

function truncateText(value, maxLength = 220) {
  const text = typeof value === "string" ? value : JSON.stringify(value);
  if (!text) {
    return "n/a";
  }
  return text.length > maxLength ? `${text.slice(0, maxLength)}...` : text;
}

async function fetchStatsPayload(snapshotDate = null) {
  const query = typeof snapshotDate === "string" && snapshotDate ? `?snapshot_date=${encodeURIComponent(snapshotDate)}` : "";
  return fetchNewsJson(`/api/news/stats${query}`);
}

function getStatsDerived(payload) {
  return asObject(asObject(payload?.data).derived);
}

function snapshotDateFromSearchParams(searchParams) {
  const raw = typeof searchParams?.snapshot === "string" ? searchParams.snapshot.trim() : "";
  return /^\d{4}-\d{2}-\d{2}$/.test(raw) ? raw : null;
}

function getQueryParam(searchParams, key) {
  const raw = searchParams?.[key];
  if (typeof raw === "string") {
    return raw.trim();
  }
  if (Array.isArray(raw) && typeof raw[0] === "string") {
    return raw[0].trim();
  }
  return "";
}

function normalizeMode(searchParams) {
  const raw = getQueryParam(searchParams, "mode").toLowerCase();
  return raw === "within-topic" ? "within-topic" : "pooled";
}

function normalizeDataMode(searchParams) {
  const raw = getQueryParam(searchParams, "data_mode").toLowerCase();
  return raw === "snapshot" ? "snapshot" : "current";
}

function selectedSnapshotDateValue(searchParams) {
  const raw = getQueryParam(searchParams, "snapshot");
  return raw || "";
}

function activeSnapshotDate(searchParams) {
  const date = snapshotDateFromSearchParams(searchParams);
  const mode = normalizeDataMode(searchParams);
  if (mode === "snapshot" && date) {
    return date;
  }
  return null;
}

function isTruthyQueryValue(raw) {
  const value = String(raw || "").trim().toLowerCase();
  return value === "1" || value === "true" || value === "yes" || value === "on";
}

function queryLimit(searchParams, key, fallback, min = 1, max = 500) {
  const raw = getQueryParam(searchParams, key);
  const parsed = Number(raw);
  if (!Number.isFinite(parsed)) {
    return fallback;
  }
  return Math.max(min, Math.min(max, Math.trunc(parsed)));
}

function selectedTopicFromQuery(searchParams, topics) {
  const requested = getQueryParam(searchParams, "topic");
  if (!requested) {
    return topics[0] || null;
  }
  return topics.find((topic) => String(topic?.topic || "") === requested) || topics[0] || null;
}

function selectSourceReliabilityView(sourceReliability, mode, selectedTopic) {
  const reliability = asObject(sourceReliability);
  const pooled = asObject(reliability.pooled);
  if (mode !== "within-topic" || !selectedTopic) {
    return pooled;
  }
  const topicRows = asArray(reliability.topics);
  const match = topicRows.find((row) => String(row?.topic || "") === selectedTopic);
  return asObject(match?.assessment) || pooled;
}

function buildQueryHref(paramsObject) {
  const queryParams = new URLSearchParams();
  for (const [key, value] of Object.entries(paramsObject || {})) {
    if (value === undefined || value === null || value === "") {
      continue;
    }
    queryParams.set(key, String(value));
  }
  const query = queryParams.toString();
  return query ? `?${query}` : "?";
}

function analysisModeQueryHref(mode, topic, dataMode, snapshot, extraParams = {}) {
  return buildQueryHref({
    ...extraParams,
    mode,
    topic,
    data_mode: dataMode,
    snapshot: dataMode === "snapshot" ? snapshot : ""
  });
}

function dataModeQueryHref(dataMode, snapshot, extraParams = {}) {
  return buildQueryHref({
    ...extraParams,
    data_mode: dataMode,
    snapshot: dataMode === "snapshot" ? snapshot : ""
  });
}

async function fetchStatsForMode(searchParams) {
  const snapshotDate = activeSnapshotDate(searchParams);
  return fetchStatsPayload(snapshotDate);
}

function PageIntro({ summary }) {
  return (
    <details className="news-page-intro">
      <summary>What this page does</summary>
      <p className="muted">{summary}</p>
    </details>
  );
}

function DataModeControls({ searchParams, extraParams = {} }) {
  const dataMode = normalizeDataMode(searchParams);
  const snapshotDateValue = selectedSnapshotDateValue(searchParams);
  const missingSnapshot = dataMode === "snapshot" && !snapshotDateFromSearchParams(searchParams);
  const currentHref = dataModeQueryHref("current", snapshotDateValue, extraParams);
  const snapshotHref = dataModeQueryHref("snapshot", snapshotDateValue, extraParams);
  return (
    <div className="panel">
      <h3>Data Mode</h3>
      <div className="top-nav-links">
        <a className={`news-nav-link ${dataMode === "current" ? "active-link" : ""}`} href={currentHref}>
          Current
        </a>
        <a className={`news-nav-link ${dataMode === "snapshot" ? "active-link" : ""}`} href={snapshotHref}>
          Snapshot
        </a>
      </div>
      <form method="get" style={{ marginTop: "10px" }}>
        {Object.entries(extraParams).map(([key, value]) => (
          <input key={key} type="hidden" name={key} value={String(value || "")} />
        ))}
        <input type="hidden" name="data_mode" value={dataMode} />
        <label className="muted" htmlFor="snapshot-date-input">
          Snapshot date
        </label>
        <div style={{ display: "flex", gap: "10px", alignItems: "center", marginTop: "6px" }}>
          <input
            id="snapshot-date-input"
            name="snapshot"
            type="date"
            defaultValue={snapshotDateValue}
            disabled={dataMode !== "snapshot"}
          />
          <button type="submit" className="news-nav-link">
            Apply
          </button>
        </div>
      </form>
      {missingSnapshot ? (
        <p className="muted" style={{ marginTop: "10px" }}>
          Snapshot mode requires a valid date (`YYYY-MM-DD`). Falling back to current data until provided.
        </p>
      ) : null}
    </div>
  );
}

function StatCard({ label, value, detail }) {
  return (
    <div className="stat-card">
      <span className="muted">{label}</span>
      <strong>{value}</strong>
      {detail ? <small className="muted">{detail}</small> : null}
    </div>
  );
}

function StatusPill({ children, tone = "neutral" }) {
  return <span className={`status-pill ${tone}`}>{children}</span>;
}

function EmptyState({ children = "No data available." }) {
  return <p className="muted">{children}</p>;
}

function StatusBlock({ status, reason }) {
  const tone = status === "ok" ? "good" : "bad";
  return (
    <p className="muted">
      <StatusPill tone={tone}>{status || "unknown"}</StatusPill>
      {reason ? ` ${reason}` : ""}
    </p>
  );
}

function MiniBar({ value, max }) {
  const number = toNumber(value) || 0;
  const limit = Math.max(toNumber(max) || 0, number, 1);
  const width = Math.max(0, Math.min(100, (number / limit) * 100));
  return (
    <div className="mini-bar" aria-label={`${formatNumber(number)} of ${formatNumber(limit)}`}>
      <span style={{ width: `${width}%` }} />
    </div>
  );
}

async function renderDigest(searchParams) {
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

async function renderStats(searchParams) {
  const payload = await fetchStatsForMode(searchParams);
  const data = payload?.data || {};
  const derived = data?.derived || {};
  const meta = payload?.meta || {};
  const summary = data?.summary || {};
  const scoreStatus = derived?.score_status || {};
  const sourceCounts = asArray(derived.source_counts).slice(0, 15);
  const tagCounts = asArray(derived.tag_counts).slice(0, 15);
  const dailyCounts = asArray(derived.daily_counts_utc);
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

async function renderSources(searchParams) {
  const payload = await fetchStatsForMode(searchParams);
  const derived = payload?.data?.derived || {};
  const sourceCounts = Array.isArray(derived?.source_counts) ? derived.source_counts : [];
  const scoredBySource = Array.isArray(derived?.chart_aggregates?.scored_by_source)
    ? derived.chart_aggregates.scored_by_source
    : [];

  const scoredLookup = new Map(
    scoredBySource
      .filter((row) => row && typeof row === "object")
      .map((row) => [String(row.source || ""), Number(row.count || 0)])
  );
  const chartRows = sourceCounts.slice(0, 20).map((row) => {
    const source = String(row.source || "Unknown");
    const count = Number(row.count || 0);
    const scored = scoredLookup.get(source) || 0;
    return {
      source,
      count,
      scored,
      coverage: count > 0 ? (scored / count) * 100 : 0
    };
  });

  return (
    <>
      <DataModeControls searchParams={searchParams} />
      <div className="panel">
        <h3>Source Charts</h3>
        {chartRows.length === 0 ? (
          <EmptyState />
        ) : (
          <div className="chart-grid">
            <PlotlyChart
              data={[
                {
                  type: "bar",
                  x: chartRows.map((row) => row.source),
                  y: chartRows.map((row) => row.count),
                  marker: { color: "#4fd1c5" }
                }
              ]}
              layout={{ title: "Article Volume by Source", yaxis: { title: "Articles" } }}
            />
            <PlotlyChart
              data={[
                {
                  type: "bar",
                  x: chartRows.map((row) => row.source),
                  y: chartRows.map((row) => row.coverage),
                  marker: { color: "#7aa7ff" }
                }
              ]}
              layout={{ title: "Scoring Coverage by Source (%)", yaxis: { title: "Coverage %", range: [0, 100] } }}
            />
          </div>
        )}
      </div>

      <div className="panel">
        <h3>Source Coverage</h3>
        {sourceCounts.length === 0 ? (
          <p className="muted">No source data available.</p>
        ) : (
          <table className="news-table">
            <thead>
              <tr>
                <th>Source</th>
                <th>Articles</th>
                <th>Scored</th>
                <th>Coverage</th>
              </tr>
            </thead>
            <tbody>
              {sourceCounts.map((row) => {
                const source = String(row.source || "Unknown");
                const count = Number(row.count || 0);
                const scored = scoredLookup.get(source) || 0;
                const coverage = count > 0 ? scored / count : null;
                return (
                  <tr key={source}>
                    <td>{source}</td>
                    <td>{formatNumber(count)}</td>
                    <td>{formatNumber(scored)}</td>
                    <td>{coverage === null ? "n/a" : `${(coverage * 100).toFixed(1)}%`}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        )}
      </div>
    </>
  );
}

async function renderLenses(searchParams) {
  const payload = await fetchStatsForMode(searchParams);
  const derived = getStatsDerived(payload);
  const lensInventory = asObject(derived.lens_inventory || asObject(payload?.data?.analysis).lens_summary);
  const lenses = asArray(lensInventory.lenses);
  const itemsTotal = toNumber(lensInventory.items_total);
  const avgRubrics =
    lenses.length > 0
      ? lenses.reduce((sum, row) => sum + (toNumber(row.rubric_count) || 0), 0) / lenses.length
      : null;
  const avgMaxScore =
    lenses.length > 0 ? lenses.reduce((sum, row) => sum + (toNumber(row.max_total) || 0), 0) / lenses.length : null;
  const lensRows = lenses.slice(0, 20).map((row) => {
    const scoredItems = toNumber(row.items_with_scores) || 0;
    const coverage = itemsTotal && scoredItems !== null ? (scoredItems / itemsTotal) * 100 : 0;
    return {
      name: String(row.name || "Unknown Lens"),
      maxTotal: toNumber(row.max_total) || 0,
      coverage
    };
  });

  return (
    <>
      <DataModeControls searchParams={searchParams} />
      <div className="panel">
        <h3>Lens Inventory</h3>
        <p className="muted">
          Coverage mode: <code>{lensInventory.coverage_mode || "unknown"}</code>
        </p>
        <div className="stats-grid">
          <StatCard label="Tracked Lenses" value={formatNumber(lenses.length)} />
          <StatCard label="Scored Items" value={formatNumber(itemsTotal)} />
          <StatCard label="Aggregation" value={lensInventory.aggregation || "n/a"} />
          <StatCard label="Avg Rubrics / Lens" value={formatDecimal(avgRubrics, 1)} />
          <StatCard label="Avg Max Score" value={formatDecimal(avgMaxScore, 1)} />
        </div>
      </div>

      <div className="panel">
        <h3>Lens Coverage</h3>
        {lensRows.length > 0 ? (
          <div className="chart-grid">
            <PlotlyChart
              data={[
                {
                  type: "bar",
                  x: lensRows.map((row) => row.name),
                  y: lensRows.map((row) => row.maxTotal),
                  marker: { color: "#4fd1c5" }
                }
              ]}
              layout={{ title: "Lens Maximum Score Capacity", yaxis: { title: "Max Score" } }}
            />
            <PlotlyChart
              data={[
                {
                  type: "bar",
                  x: lensRows.map((row) => row.name),
                  y: lensRows.map((row) => row.coverage),
                  marker: { color: "#7aa7ff" }
                }
              ]}
              layout={{ title: "Lens Coverage Across Articles (%)", yaxis: { title: "Coverage %", range: [0, 100] } }}
            />
          </div>
        ) : null}
        {lenses.length === 0 ? (
          <EmptyState />
        ) : (
          <table className="news-table">
            <thead>
              <tr>
                <th>Lens</th>
                <th>Rubrics</th>
                <th>Max Total</th>
                <th>Items with Scores</th>
                <th>Coverage</th>
              </tr>
            </thead>
            <tbody>
              {lenses.map((row) => {
                const name = String(row.name || "Unknown Lens");
                const scoredItems = toNumber(row.items_with_scores);
                const coverage = itemsTotal && scoredItems !== null ? scoredItems / itemsTotal : null;
                return (
                  <tr key={name}>
                    <td>{name}</td>
                    <td>{formatNumber(row.rubric_count)}</td>
                    <td>{formatDecimal(row.max_total, 1)}</td>
                    <td>{formatNumber(scoredItems)}</td>
                    <td>
                      {formatPercent(coverage)}
                      <MiniBar value={coverage || 0} max={1} />
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        )}
      </div>
    </>
  );
}

async function renderTags(searchParams) {
  const payload = await fetchStatsForMode(searchParams);
  const derived = getStatsDerived(payload);
  const chartAggregates = asObject(derived.chart_aggregates);
  const sourceTagViews = asObject(derived.source_tag_views);
  const tagCounts = asArray(derived.tag_counts).slice(0, 30);
  const tagDistribution = asArray(chartAggregates.tag_count_distribution);
  const sourceTagMatrixRows = asArray(chartAggregates.source_tag_matrix);
  const sourceLabels = asArray(sourceTagViews.source_labels).slice(0, 10);
  const tagLabels = asArray(sourceTagViews.tag_labels).slice(0, 12);
  const matrixLookup = new Map(
    sourceTagMatrixRows.map((row) => [pairKey(row.source, row.tag), toNumber(row.count) || 0])
  );
  const matrix = sourceLabels.map((source) => tagLabels.map((tag) => matrixLookup.get(pairKey(source, tag)) || 0));
  const maxTagCount = tagCounts.reduce((max, row) => Math.max(max, toNumber(row.count) || 0), 0);

  return (
    <>
      <DataModeControls searchParams={searchParams} />
      <div className="panel">
        <h3>Top Tags</h3>
        {tagCounts.length > 0 ? (
          <div className="chart-grid">
            <PlotlyChart
              data={[
                {
                  type: "bar",
                  orientation: "h",
                  y: tagCounts.map((row) => String(row.tag || "Unknown")).reverse(),
                  x: tagCounts.map((row) => toNumber(row.count) || 0).reverse(),
                  marker: { color: "#fd7e14" }
                }
              ]}
              layout={{ title: "Top Tags", xaxis: { title: "Articles" } }}
            />
            <PlotlyChart
              data={[
                {
                  type: "bar",
                  x: tagDistribution.map((row) => String(row.label || "Unknown")),
                  y: tagDistribution.map((row) => toNumber(row.count) || 0),
                  marker: { color: "#4fd1c5" }
                }
              ]}
              layout={{ title: "Tags per Article Distribution", yaxis: { title: "Articles" } }}
            />
            <PlotlyChart
              data={[
                {
                  type: "heatmap",
                  x: tagLabels,
                  y: sourceLabels,
                  z: matrix,
                  colorscale: "Viridis"
                }
              ]}
              layout={{ title: "Source x Tag Intensity" }}
            />
          </div>
        ) : null}
        {tagCounts.length === 0 ? (
          <EmptyState />
        ) : (
          <table className="news-table">
            <thead>
              <tr>
                <th>Tag</th>
                <th>Articles</th>
                <th>Relative Frequency</th>
              </tr>
            </thead>
            <tbody>
              {tagCounts.map((row) => (
                <tr key={String(row.tag || "unknown")}>
                  <td>{row.tag || "Unknown"}</td>
                  <td>{formatNumber(row.count)}</td>
                  <td>
                    <MiniBar value={row.count} max={maxTagCount} />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      <div className="panel">
        <h3>Tags Per Article</h3>
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
      </div>
    </>
  );
}

async function renderSourceTagMatrix(searchParams) {
  const payload = await fetchStatsForMode(searchParams);
  const derived = getStatsDerived(payload);
  const chartAggregates = asObject(derived.chart_aggregates);
  const sourceTagViews = asObject(derived.source_tag_views);
  const summary = asObject(sourceTagViews.summary);
  const topSources = queryLimit(searchParams, "top_sources", 10, 3, 30);
  const topTags = queryLimit(searchParams, "top_tags", 15, 5, 40);
  const topN = queryLimit(searchParams, "top_n", 10, 3, 30);
  const sourceRows = asArray(sourceTagViews.source_rows);
  const sourceSlice = sourceRows.slice(0, topSources);
  const sourceLabels = sourceSlice.map((row) => String(row?.source || "Unknown")).filter(Boolean);
  const tagLabels = asArray(sourceTagViews.tag_labels).slice(0, topTags).filter(Boolean);
  const matrixRows = asArray(chartAggregates.source_tag_matrix);
  const sourceTotals = sourceSlice.map((row) => ({
    source: String(row?.source || "Unknown"),
    count: toNumber(row?.count) || 0
  }));
  const sourceParam = String(getQueryParam(searchParams, "source") || "").trim();
  const selectedSource = sourceLabels.includes(sourceParam) ? sourceParam : sourceLabels[0] || "";
  const selectedSourceRow = sourceSlice.find((row) => String(row?.source || "") === selectedSource) || null;
  const selectedSourceTags = asArray(selectedSourceRow?.tags)
    .filter((row) => String(row?.tag || "").trim() && String(row?.tag || "").trim().toLowerCase() !== "general")
    .slice(0, topN);
  const dataMode = normalizeDataMode(searchParams);
  const snapshotDateValue = selectedSnapshotDateValue(searchParams);
  const matrixRowsCount = toNumber(summary.matrix_rows) ?? matrixRows.length;
  const nonZeroCells = toNumber(summary.non_zero_cells) ?? matrixRows.filter((row) => (toNumber(row?.count) || 0) > 0).length;
  const lookup = new Map(
    matrixRows.map((row) => [pairKey(row.source, row.tag), toNumber(row.count) || 0])
  );
  const matrix = sourceLabels.map((source) => tagLabels.map((tag) => lookup.get(pairKey(source, tag)) || 0));

  return (
    <>
      <DataModeControls
        searchParams={searchParams}
        extraParams={{
          top_sources: topSources,
          top_tags: topTags,
          top_n: topN,
          source: selectedSource
        }}
      />
      <div className="panel">
        <h3>Source Tag Filters</h3>
        <form method="get">
          <input type="hidden" name="data_mode" value={dataMode} />
          <input type="hidden" name="snapshot" value={dataMode === "snapshot" ? snapshotDateValue : ""} />
          <div className="filter-grid">
            <label>
              Top Sources
              <input type="number" name="top_sources" min="3" max="30" defaultValue={topSources} />
            </label>
            <label>
              Top Tags
              <input type="number" name="top_tags" min="5" max="40" defaultValue={topTags} />
            </label>
            <label>
              Selected Source
              <select name="source" defaultValue={selectedSource}>
                {sourceLabels.map((source) => (
                  <option key={source} value={source}>
                    {source}
                  </option>
                ))}
              </select>
            </label>
            <label>
              Selected Source Top Tags
              <input type="number" name="top_n" min="3" max="30" defaultValue={topN} />
            </label>
          </div>
          <button type="submit" className="news-nav-link" style={{ marginTop: "12px" }}>
            Apply
          </button>
        </form>
      </div>

      <div className="panel">
        <h3>Source Tag Summary</h3>
        <div className="stats-grid">
          <StatCard label="Sources in View" value={formatNumber(sourceLabels.length)} />
          <StatCard label="Tags in View" value={formatNumber(tagLabels.length)} />
          <StatCard label="Non-zero Cells" value={formatNumber(nonZeroCells)} />
          <StatCard label="Matrix Rows" value={formatNumber(matrixRowsCount)} />
        </div>
      </div>

      <div className="panel">
        <h3>Matrix Visuals</h3>
        {sourceLabels.length === 0 || tagLabels.length === 0 ? (
          <EmptyState />
        ) : (
          <div className="chart-grid">
            <PlotlyChart
              data={[
                {
                  type: "heatmap",
                  x: tagLabels,
                  y: sourceLabels,
                  z: matrix,
                  colorscale: "Viridis"
                }
              ]}
              layout={{ title: "Source x Tag Intensity Heatmap" }}
            />
            <PlotlyChart
              data={[
                {
                  type: "bar",
                  x: sourceTotals.map((row) => String(row.source || "Unknown")),
                  y: sourceTotals.map((row) => toNumber(row.count) || 0),
                  marker: { color: "#7aa7ff" }
                }
              ]}
              layout={{ title: "Source Tag Totals", yaxis: { title: "Tag Assignments" } }}
            />
          </div>
        )}
      </div>

      <div className="panel">
        <h3>Selected Source Top Tags</h3>
        {selectedSourceTags.length === 0 ? (
          <EmptyState children="No tags are available for the selected source." />
        ) : (
          <PlotlyChart
            data={[
              {
                type: "bar",
                orientation: "h",
                x: selectedSourceTags.map((row) => toNumber(row?.count) || 0),
                y: selectedSourceTags.map((row) => String(row?.tag || "")),
                marker: { color: "#198754" }
              }
            ]}
            layout={{ title: `Top Tags for ${selectedSource}`, yaxis: { autorange: "reversed" }, xaxis: { title: "Count" } }}
          />
        )}
      </div>
      <div className="panel">
        <h3>Source x Tag Matrix</h3>
        <p className="muted">Showing the top {formatNumber(sourceLabels.length)} sources and top {formatNumber(tagLabels.length)} tags.</p>
        {sourceLabels.length === 0 || tagLabels.length === 0 ? (
          <EmptyState />
        ) : (
          <div className="table-scroll">
            <table className="news-table">
              <thead>
                <tr>
                  <th>Source</th>
                  {tagLabels.map((tag) => (
                    <th key={tag}>{tag}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {sourceLabels.map((source) => (
                  <tr key={source}>
                    <td>{source}</td>
                    {tagLabels.map((tag) => (
                      <td key={`${source}-${tag}`}>{formatNumber(lookup.get(pairKey(source, tag)) || 0)}</td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      <div className="panel">
        <h3>Selected Source Tag Table</h3>
        {selectedSourceTags.length === 0 ? (
          <EmptyState children="No tags are available for the selected source." />
        ) : (
          <table className="news-table compact">
            <thead>
              <tr>
                <th>Tag</th>
                <th>Count</th>
              </tr>
            </thead>
            <tbody>
              {selectedSourceTags.map((row) => (
                <tr key={String(row?.tag || "")}>
                  <td>{String(row?.tag || "")}</td>
                  <td>{formatNumber(toNumber(row?.count) || 0)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      <div className="panel">
        <h3>Source Tag Totals</h3>
        {sourceTotals.length === 0 ? (
          <EmptyState />
        ) : (
          <table className="news-table compact">
            <thead>
              <tr>
                <th>Source</th>
                <th>Tag Assignments</th>
              </tr>
            </thead>
            <tbody>
              {sourceTotals.map((row) => (
                <tr key={String(row.source || "unknown")}>
                  <td>{row.source || "Unknown"}</td>
                  <td>{formatNumber(row.count)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </>
  );
}

async function renderTrends(searchParams) {
  const payload = await fetchStatsForMode(searchParams);
  const derived = getStatsDerived(payload);
  const chartAggregates = asObject(derived.chart_aggregates);
  const dailyCounts = asArray(derived.daily_counts_utc);
  const hourCounts = asArray(chartAggregates.publish_hour_counts_utc);
  const maxDailyCount = dailyCounts.reduce((max, row) => Math.max(max, toNumber(row.count) || 0), 0);
  const maxHourCount = hourCounts.reduce((max, row) => Math.max(max, toNumber(row.count) || 0), 0);
  const firstDate = dailyCounts[0]?.date || "n/a";
  const lastDate = dailyCounts[dailyCounts.length - 1]?.date || "n/a";

  return (
    <>
      <DataModeControls searchParams={searchParams} />
      <div className="panel">
        <h3>Temporal Coverage</h3>
        <div className="stats-grid">
          <StatCard label="Days Covered" value={formatNumber(dailyCounts.length)} />
          <StatCard label="First Day" value={firstDate} />
          <StatCard label="Latest Day" value={lastDate} />
          <StatCard label="Articles" value={formatNumber(derived.total_articles)} />
        </div>
      </div>

      <div className="panel">
        <h3>Daily Article Counts</h3>
        {dailyCounts.length > 0 ? (
          <div className="chart-grid">
            <PlotlyChart
              data={[
                {
                  type: "scatter",
                  mode: "lines+markers",
                  x: dailyCounts.map((row) => String(row.date || "")),
                  y: dailyCounts.map((row) => toNumber(row.count) || 0),
                  line: { color: "#4fd1c5" }
                }
              ]}
              layout={{ title: "Daily Articles (UTC)", yaxis: { title: "Articles" } }}
            />
            <PlotlyChart
              data={[
                {
                  type: "bar",
                  x: hourCounts.map((row) => String(row.hour).padStart(2, "0")),
                  y: hourCounts.map((row) => toNumber(row.count) || 0),
                  marker: { color: "#7aa7ff" }
                }
              ]}
              layout={{ title: "Publish Hour Distribution (UTC)", xaxis: { title: "Hour" }, yaxis: { title: "Articles" } }}
            />
          </div>
        ) : null}
        {dailyCounts.length === 0 ? (
          <EmptyState />
        ) : (
          <table className="news-table compact">
            <thead>
              <tr>
                <th>Date</th>
                <th>Articles</th>
                <th>Volume</th>
              </tr>
            </thead>
            <tbody>
              {dailyCounts.map((row) => (
                <tr key={String(row.date)}>
                  <td>{row.date}</td>
                  <td>{formatNumber(row.count)}</td>
                  <td>
                    <MiniBar value={row.count} max={maxDailyCount} />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      <div className="panel">
        <h3>Publish Hours (UTC)</h3>
        {hourCounts.length === 0 ? (
          <EmptyState />
        ) : (
          <table className="news-table compact">
            <tbody>
              {hourCounts.map((row) => (
                <tr key={String(row.hour)}>
                  <th>{String(row.hour).padStart(2, "0")}:00</th>
                  <td>{formatNumber(row.count)}</td>
                  <td>
                    <MiniBar value={row.count} max={maxHourCount} />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </>
  );
}

async function renderDataQuality(searchParams) {
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

async function fetchEndpointStatus(label, path, options = {}) {
  const fetchOptions = asObject(options?.fetchOptions);
  const url = `${newsApiBaseUrl()}${path}`;
  try {
    const response = await fetch(url, {
      next: { revalidate: 60 },
      ...fetchOptions
    });
    const statusCode = response.status;
    const text = await response.text();
    let payload = null;
    try {
      payload = text ? JSON.parse(text) : null;
    } catch (_error) {
      payload = text;
    }
    const payloadObj = asObject(payload);
    const meta = asObject(payloadObj?.meta);
    const payloadData = asObject(payloadObj?.data);
    return {
      label,
      path,
      ok: response.ok,
      status: response.ok ? "ok" : "error",
      statusCode,
      detail:
        meta?.source_mode ||
        payloadData?.status ||
        payloadObj?.status ||
        (typeof payload === "string" && payload ? truncateText(payload, 200) : "reachable"),
      payload
    };
  } catch (error) {
    return {
      label,
      path,
      ok: false,
      status: "error",
      statusCode: null,
      detail: error instanceof Error ? error.message : String(error),
      payload: null
    };
  }
}

function EndpointTable({ rows }) {
  return (
    <table className="news-table">
      <thead>
        <tr>
          <th>Check</th>
          <th>Endpoint</th>
          <th>Status</th>
          <th>Detail</th>
        </tr>
      </thead>
      <tbody>
        {rows.map((row) => (
          <tr key={row.path}>
            <td>{row.label}</td>
            <td>
              <code>{row.path}</code>
            </td>
            <td>
              <StatusPill tone={row.ok ? "good" : "bad"}>
                {row.statusCode ? `HTTP ${row.statusCode}` : row.status}
              </StatusPill>
            </td>
            <td>{truncateText(row.detail)}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

async function renderWorkflowStatus(searchParams) {
  const dataMode = normalizeDataMode(searchParams);
  const snapshotDate = activeSnapshotDate(searchParams);
  const forceRefresh = isTruthyQueryValue(getQueryParam(searchParams, "refresh"));
  const requestOptions = forceRefresh ? { fetchOptions: { cache: "no-store" } } : {};

  const commonParams = new URLSearchParams();
  if (snapshotDate) {
    commonParams.set("snapshot_date", snapshotDate);
  }
  if (forceRefresh) {
    commonParams.set("refresh", "true");
  }

  const digestPath = `/api/news/digest?${new URLSearchParams({ ...Object.fromEntries(commonParams), limit: "1" }).toString()}`;
  const latestPath = `/api/news/digest/latest${commonParams.toString() ? `?${commonParams.toString()}` : ""}`;
  const statsPath = `/api/news/stats${commonParams.toString() ? `?${commonParams.toString()}` : ""}`;
  const freshnessPath =
    dataMode === "current" && forceRefresh ? "/health/news-freshness?refresh=true" : "/health/news-freshness";

  const rows = await Promise.all([
    fetchEndpointStatus("Digest", digestPath, requestOptions),
    fetchEndpointStatus("Latest", latestPath, requestOptions),
    fetchEndpointStatus("Stats", statsPath, requestOptions),
    fetchEndpointStatus("Freshness", freshnessPath, requestOptions)
  ]);
  const digestRow = rows[0];
  const latestRow = rows[1];
  const statsRow = rows[2];
  const freshnessRow = rows[3];

  const digestMeta = asObject(asObject(digestRow?.payload).meta);
  const statsPayload = asObject(statsRow?.payload);
  const statsMeta = asObject(statsPayload.meta);
  const derived = asObject(asObject(statsPayload.data).derived);
  const latestRecord = asObject(asObject(latestRow?.payload).data);

  const inputArticles = toNumber(digestMeta.input_articles_count);
  const excludedUnscraped = toNumber(digestMeta.excluded_unscraped_articles);
  const includedArticles = toNumber(derived.total_articles);
  const scoredArticles = toNumber(derived.scored_articles);
  const zeroScoreArticles = toNumber(derived.zero_score_articles);
  const unscorableArticles = toNumber(derived.unscorable_articles);
  const scoreCoverageRatio = toNumber(derived.score_coverage_ratio);
  const freshnessPayload = asObject(freshnessRow?.payload);

  const ingestOk = digestRow?.ok;
  const scrapeFilterOk =
    inputArticles !== null &&
    excludedUnscraped !== null &&
    includedArticles !== null &&
    inputArticles >= includedArticles &&
    excludedUnscraped >= 0;
  const scoringOk = Boolean(statsRow?.ok) && scoredArticles !== null && scoredArticles > 0;
  const unscorableOk = Boolean(statsRow?.ok) && unscorableArticles !== null && unscorableArticles === 0;
  const precomputeOk = Boolean(statsRow?.ok) && Boolean(statsMeta.schema_version);
  const freshnessOk = dataMode === "snapshot" ? null : Boolean(freshnessRow?.ok);
  const freshnessLabel =
    dataMode === "snapshot"
      ? "Snapshot mode does not use freshness health gate."
      : `current freshness endpoint -> HTTP ${freshnessRow?.statusCode || "n/a"}; is_fresh=${String(freshnessPayload.is_fresh)}`;

  const sourceInfo = asObject(latestRecord.source);
  const latestTitle = latestRecord.title || "Latest article unavailable";
  const latestSource = sourceInfo.name || sourceInfo.id || "Unknown source";
  const latestPublished = latestRecord.published_at || latestRecord.published || "Unknown date";

  const modeText = dataMode === "snapshot" ? "Snapshot mode" : "Current mode";
  const refreshHref = buildQueryHref({
    data_mode: dataMode,
    snapshot: dataMode === "snapshot" ? selectedSnapshotDateValue(searchParams) : "",
    refresh: "1"
  });

  return (
    <>
      <DataModeControls searchParams={searchParams} />
      <div className="panel">
        <h3>Pipeline Snapshot</h3>
        <div className="stats-grid">
          <StatCard label="Input Articles" value={formatNumber(inputArticles)} />
          <StatCard label="Excluded (Scrape Errors)" value={formatNumber(excludedUnscraped)} />
          <StatCard label="Included Articles" value={formatNumber(includedArticles)} />
          <StatCard label="Scored Articles" value={formatNumber(scoredArticles)} />
          <StatCard label="Zero Scores" value={formatNumber(zeroScoreArticles)} />
          <StatCard label="Unscorable" value={formatNumber(unscorableArticles)} />
          <StatCard label="Coverage" value={formatPercent(scoreCoverageRatio)} />
        </div>
        <p className="muted">
          {modeText}
          {snapshotDate ? (
            <>
              {" "}
              for snapshot <code>{snapshotDate}</code>
            </>
          ) : null}
          . <a href={refreshHref}>Refresh checks</a>
        </p>
      </div>

      <div className="panel">
        <h3>Runtime Checks</h3>
        <ul className="news-list compact">
          <li>
            Ingest + digest endpoint:{" "}
            <StatusPill tone={ingestOk ? "good" : "bad"}>{ingestOk ? "PASS" : "FAIL"}</StatusPill>
          </li>
          <li>
            Scrape filtering in effect:{" "}
            <StatusPill tone={scrapeFilterOk ? "good" : "bad"}>{scrapeFilterOk ? "PASS" : "FAIL"}</StatusPill>
          </li>
          <li>
            Rubric scoring present:{" "}
            <StatusPill tone={scoringOk ? "good" : "bad"}>{scoringOk ? "PASS" : "FAIL"}</StatusPill>
          </li>
          <li>
            Unscorable article gate:{" "}
            <StatusPill tone={unscorableOk ? "good" : "warn"}>{unscorableOk ? "PASS" : "WARN"}</StatusPill>
          </li>
          <li>
            Precomputed contract present:{" "}
            <StatusPill tone={precomputeOk ? "good" : "bad"}>{precomputeOk ? "PASS" : "FAIL"}</StatusPill>
          </li>
          <li>
            Freshness gate:{" "}
            <StatusPill tone={dataMode === "snapshot" ? "warn" : freshnessOk ? "good" : "bad"}>
              {dataMode === "snapshot" ? "WARN" : freshnessOk ? "PASS" : "FAIL"}
            </StatusPill>{" "}
            <span className="muted">{freshnessLabel}</span>
          </li>
        </ul>
        <EndpointTable rows={rows} />
      </div>

      <div className="panel">
        <h3>Latest Article</h3>
        {latestRecord?.title ? (
          <>
            <p>
              <strong>{latestTitle}</strong>
            </p>
            <p className="muted">
              Source: {latestSource}
              <br />
              Published (UTC): {latestPublished}
            </p>
            <p>{latestRecord.ai_summary || latestRecord.summary || "No summary available."}</p>
            {latestRecord.link ? (
              <p>
                <a href={latestRecord.link} target="_blank" rel="noreferrer">
                  Open Article
                </a>
              </p>
            ) : null}
          </>
        ) : (
          <EmptyState>Latest article unavailable for current filters.</EmptyState>
        )}
      </div>
    </>
  );
}

async function renderRawJson(searchParams) {
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

async function renderIntegration(searchParams) {
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

function getCorrelationPairRows(lenses, matrix) {
  const rows = [];
  for (let i = 0; i < lenses.length; i += 1) {
    for (let j = i + 1; j < lenses.length; j += 1) {
      const value = toNumber(asArray(matrix[i])[j]);
      if (value !== null) {
        rows.push({ lens_a: lenses[i], lens_b: lenses[j], value });
      }
    }
  }
  rows.sort((a, b) => Math.abs(b.value) - Math.abs(a.value));
  return rows;
}

function sourceCountsToRows(sourceCountsValue) {
  if (Array.isArray(sourceCountsValue)) {
    return sourceCountsValue
      .map((row) => ({
        source: String(row?.source || "Unknown"),
        count: toNumber(row?.count) || 0
      }))
      .sort((a, b) => b.count - a.count || a.source.localeCompare(b.source));
  }
  const sourceCounts = asObject(sourceCountsValue);
  return Object.entries(sourceCounts)
    .map(([source, count]) => ({
      source: String(source || "Unknown"),
      count: toNumber(count) || 0
    }))
    .sort((a, b) => b.count - a.count || a.source.localeCompare(b.source));
}

function normalizedSourceEffectsFilter(searchParams) {
  const allowedMaxLens = new Set([5, 10, 15, 20]);
  const allowedQThreshold = new Set([1.0, 0.1, 0.05, 0.01]);
  const maxLensesRaw = queryLimit(searchParams, "max_lenses", 10, 1, 20);
  const qThresholdRaw = toNumber(getQueryParam(searchParams, "q_threshold"));
  return {
    maxLenses: allowedMaxLens.has(maxLensesRaw) ? maxLensesRaw : 10,
    qThreshold: qThresholdRaw !== null && allowedQThreshold.has(qThresholdRaw) ? qThresholdRaw : 1.0
  };
}

async function renderLensMatrix(searchParams) {
  const payload = await fetchStatsForMode(searchParams);
  const derived = getStatsDerived(payload);
  const lensViews = asObject(derived.lens_views);
  const lensNames = asArray(lensViews.lens_names);
  const sourceRows = asArray(lensViews.source_rows);
  const summary = asObject(lensViews.summary);
  const topRows = sourceRows.slice(0, 20);
  const lensAverageRows = asArray(summary.source_lens_average_rows)
    .map((row) => ({
      lens: String(row?.lens || ""),
      mean: toNumber(row?.mean)
    }))
    .filter((row) => row.lens && row.mean !== null)
    .sort((a, b) => (b.mean || 0) - (a.mean || 0));
  const focusLens = lensAverageRows[0]?.lens || lensNames[0] || null;
  const matrix = topRows.map((row) => {
    const means = asObject(row.lens_means);
    return lensNames.map((lens) => toNumber(means[lens]) || 0);
  });

  return (
    <>
      <DataModeControls searchParams={searchParams} />
      <div className="panel">
        <h3>Lens Matrix Summary</h3>
        <div className="stats-grid">
          <StatCard label="Coverage Mode" value={lensViews.coverage_mode || "n/a"} />
          <StatCard label="Sources" value={formatNumber(summary.source_count || sourceRows.length)} />
          <StatCard label="Lenses" value={formatNumber(lensNames.length)} />
          <StatCard label="Covered Articles" value={formatNumber(summary.covered_articles)} />
        </div>
      </div>

      <div className="panel">
        <h3>Lens Matrix Visuals</h3>
        {topRows.length === 0 || lensNames.length === 0 ? (
          <EmptyState />
        ) : (
          <div className="chart-grid">
            <PlotlyChart
              data={[
                {
                  type: "heatmap",
                  x: lensNames,
                  y: topRows.map((row) => String(row.source || "Unknown")),
                  z: matrix,
                  colorscale: "Viridis"
                }
              ]}
              layout={{ title: "Source x Lens Mean Heatmap (Percent Scale)" }}
            />
            <PlotlyChart
              data={[
                {
                  type: "bar",
                  x: topRows.map((row) => String(row.source || "Unknown")),
                  y: topRows.map((row) => {
                    const means = asObject(row.lens_means);
                    return focusLens ? toNumber(means[focusLens]) || 0 : 0;
                  }),
                  marker: { color: "#7aa7ff" }
                }
              ]}
              layout={{
                title: `Source Means for Focus Lens: ${focusLens || "n/a"}`,
                yaxis: { title: "Percent" }
              }}
            />
          </div>
        )}
      </div>

      <div className="panel">
        <h3>Top Sources x Lenses</h3>
        {topRows.length === 0 || lensNames.length === 0 ? (
          <EmptyState />
        ) : (
          <div className="table-scroll">
            <table className="news-table compact">
              <thead>
                <tr>
                  <th>Source</th>
                  <th>Articles</th>
                  {lensNames.map((lens) => (
                    <th key={lens}>{lens}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {topRows.map((row) => {
                  const means = asObject(row.lens_means);
                  return (
                    <tr key={String(row.source || "unknown")}>
                      <td>{row.source || "Unknown"}</td>
                      <td>{formatNumber(row.article_count)}</td>
                      {lensNames.map((lens) => (
                        <td key={`${row.source}-${lens}`}>{formatAlreadyPercent(means[lens])}</td>
                      ))}
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </>
  );
}

async function renderLensCorrelations(searchParams) {
  const payload = await fetchStatsForMode(searchParams);
  const derived = getStatsDerived(payload);
  const correlations = asObject(derived.lens_correlations);
  const lenses = asArray(correlations.lenses);
  const corrRaw = asArray(asObject(correlations.correlation).raw);
  const pairRankings = asArray(asObject(correlations.pair_rankings).corr_raw);
  const rawTopPairs =
    pairRankings.length > 0
      ? pairRankings
          .map((row) => ({
            lens_a: row?.lens_a,
            lens_b: row?.lens_b,
            value: toNumber(row?.value)
          }))
          .filter((row) => row.lens_a && row.lens_b && row.value !== null)
      : getCorrelationPairRows(lenses, corrRaw);
  const topPairs = rawTopPairs.slice(0, 25);
  const matrix = lenses.map((_, rowIndex) =>
    lenses.map((_, colIndex) => toNumber(asArray(corrRaw[rowIndex])[colIndex]) || 0)
  );

  return (
    <>
      <DataModeControls searchParams={searchParams} />
      <div className="panel">
        <h3>Correlation Summary</h3>
        <div className="stats-grid">
          <StatCard label="Lenses" value={formatNumber(lenses.length)} />
          <StatCard label="Pairs" value={formatNumber(topPairs.length)} />
          <StatCard label="Matrixes" value="corr/cov/pairwise" />
        </div>
      </div>

      <div className="panel">
        <h3>Correlation Visuals</h3>
        {lenses.length === 0 ? (
          <EmptyState />
        ) : (
          <div className="chart-grid">
            <PlotlyChart
              data={[
                {
                  type: "heatmap",
                  x: lenses,
                  y: lenses,
                  z: matrix,
                  zmin: -1,
                  zmax: 1,
                  colorscale: "RdBu"
                }
              ]}
              layout={{ title: "Lens Correlation Heatmap (Raw)" }}
            />
            <PlotlyChart
              data={[
                {
                  type: "bar",
                  orientation: "h",
                  y: topPairs
                    .map((row) => `${row.lens_a} vs ${row.lens_b}`)
                    .reverse(),
                  x: topPairs.map((row) => toNumber(row.value) || 0).reverse(),
                  marker: {
                    color: topPairs.map((row) => (toNumber(row.value) || 0)).reverse(),
                    colorscale: "RdBu"
                  }
                }
              ]}
              layout={{ title: "Top Correlation Pairs (Signed)", xaxis: { title: "Correlation" } }}
            />
          </div>
        )}
      </div>

      <div className="panel">
        <h3>Top Lens Pairs (Correlation Raw)</h3>
        {rawTopPairs.length === 0 ? (
          <EmptyState />
        ) : (
          <table className="news-table compact">
            <thead>
              <tr>
                <th>Lens A</th>
                <th>Lens B</th>
                <th>Correlation</th>
              </tr>
            </thead>
            <tbody>
              {rawTopPairs.slice(0, 25).map((row, index) => (
                <tr key={`${row.lens_a}-${row.lens_b}-${index}`}>
                  <td>{row.lens_a}</td>
                  <td>{row.lens_b}</td>
                  <td>{formatDecimal(row.value, 4)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </>
  );
}

async function renderLensPca(searchParams) {
  const payload = await fetchStatsForMode(searchParams);
  const derived = getStatsDerived(payload);
  const pca = asObject(derived.lens_pca);
  const mds = asObject(derived.lens_mds);
  const lensTimeSeries = asObject(derived.lens_time_series);
  const temporalPca = asObject(derived.lens_temporal_embedding);
  const temporalMds = asObject(derived.lens_temporal_embedding_mds);
  const explained = asArray(pca.explained_variance);
  const drivers = asArray(pca.variance_drivers);
  const centroids = asArray(pca.source_centroids);
  const loadings = asObject(pca.loadings);
  const loadingLenses = asArray(loadings.lenses).map((value) => String(value || ""));
  const loadingComponents = asArray(loadings.components).map((value) => String(value || ""));
  const loadingMatrixRaw = asArray(loadings.matrix);
  const loadingMatrix = loadingMatrixRaw.map((row) =>
    asArray(row).slice(0, loadingLenses.length).map((value) => toNumber(value) || 0)
  );
  const maxAbsLoading = Math.max(...loadingMatrix.flat().map((value) => Math.abs(value)), 1);
  const selectedComponent = loadingComponents[0] || null;
  const selectedComponentIndex = selectedComponent ? loadingComponents.indexOf(selectedComponent) : -1;
  const selectedLoadings =
    selectedComponentIndex >= 0 && selectedComponentIndex < loadingMatrix.length
      ? loadingLenses
          .map((lens, lensIndex) => ({ lens, loading: toNumber(loadingMatrix[selectedComponentIndex][lensIndex]) || 0 }))
          .sort((a, b) => Math.abs(b.loading) - Math.abs(a.loading))
      : [];
  const componentSummaryRows = asArray(pca.component_summary);
  const timeSeriesRows = asArray(lensTimeSeries.series)
    .map((row) => ({
      lens: String(row?.lens || ""),
      points: asArray(row?.points)
        .map((point) => ({
          date: String(point?.date || ""),
          mean: toNumber(point?.mean),
          median: toNumber(point?.median),
          min: toNumber(point?.min),
          max: toNumber(point?.max),
          count: toNumber(point?.count)
        }))
        .filter((point) => point.date && point.mean !== null)
    }))
    .filter((row) => row.lens && row.points.length > 0)
    .sort((a, b) => {
      const aMaxCount = Math.max(...a.points.map((point) => point.count || 0), 0);
      const bMaxCount = Math.max(...b.points.map((point) => point.count || 0), 0);
      if (bMaxCount !== aMaxCount) {
        return bMaxCount - aMaxCount;
      }
      return a.lens.localeCompare(b.lens);
    })
    .slice(0, 8);
  const temporalPcaPointRows = asArray(temporalPca.points)
    .map((row) => ({
      title: String(row?.title || "Untitled"),
      source: String(row?.source || "Unknown"),
      date: String(row?.date || ""),
      strongestLens: String(row?.strongest_lens || "Unknown"),
      dayIndex: toNumber(row?.day_index),
      pc1: toNumber(row?.pc1),
      pc2: toNumber(row?.pc2)
    }))
    .filter((row) => row.dayIndex !== null && row.pc1 !== null && row.pc2 !== null);
  const temporalPcaCentroidRows = asArray(temporalPca.day_centroids)
    .map((row) => ({
      date: String(row?.date || ""),
      dayIndex: toNumber(row?.day_index),
      count: toNumber(row?.count) || 0,
      pc1: toNumber(row?.pc1),
      pc2: toNumber(row?.pc2)
    }))
    .filter((row) => row.dayIndex !== null && row.pc1 !== null && row.pc2 !== null)
    .sort((a, b) => (a.dayIndex || 0) - (b.dayIndex || 0));
  const temporalMdsPointRows = asArray(temporalMds.points)
    .map((row) => ({
      title: String(row?.title || "Untitled"),
      source: String(row?.source || "Unknown"),
      date: String(row?.date || ""),
      strongestLens: String(row?.strongest_lens || "Unknown"),
      dayIndex: toNumber(row?.day_index),
      mds1: toNumber(row?.mds1),
      mds2: toNumber(row?.mds2)
    }))
    .filter((row) => row.dayIndex !== null && row.mds1 !== null && row.mds2 !== null);
  const temporalMdsCentroidRows = asArray(temporalMds.day_centroids)
    .map((row) => ({
      date: String(row?.date || ""),
      dayIndex: toNumber(row?.day_index),
      mds1: toNumber(row?.mds1),
      mds2: toNumber(row?.mds2)
    }))
    .filter((row) => row.dayIndex !== null && row.mds1 !== null && row.mds2 !== null)
    .sort((a, b) => (a.dayIndex || 0) - (b.dayIndex || 0));
  const explainedRows = explained
    .map((row) => ({
      component: String(row?.component || ""),
      explained: toNumber(row?.explained_variance_ratio),
      cumulative: toNumber(row?.cumulative_variance_ratio)
    }))
    .filter((row) => row.component && row.explained !== null && row.cumulative !== null);
  const centroidRows = centroids
    .map((row) => ({
      source: String(row?.source || "Unknown"),
      count: toNumber(row?.count) || 0,
      pc1: toNumber(row?.pc1),
      pc2: toNumber(row?.pc2)
    }))
    .filter((row) => row.pc1 !== null && row.pc2 !== null);
  const pcaArticleRows = asArray(pca.article_points)
    .map((row) => ({
      title: String(row?.title || "Untitled"),
      source: String(row?.source || "Unknown"),
      strongestLens: String(row?.strongest_lens || "Unknown"),
      publishedAt: String(row?.published_at || "Unknown"),
      pc1: toNumber(row?.pc1),
      pc2: toNumber(row?.pc2)
    }))
    .filter((row) => row.pc1 !== null && row.pc2 !== null);
  const mdsArticleRows = asArray(mds.article_points)
    .map((row) => ({
      title: String(row?.title || "Untitled"),
      source: String(row?.source || "Unknown"),
      strongestLens: String(row?.strongest_lens || "Unknown"),
      publishedAt: String(row?.published_at || "Unknown"),
      mds1: toNumber(row?.mds1),
      mds2: toNumber(row?.mds2)
    }))
    .filter((row) => row.mds1 !== null && row.mds2 !== null);
  const mdsCentroidRows = asArray(mds.source_centroids)
    .map((row) => ({
      source: String(row?.source || "Unknown"),
      mds1: toNumber(row?.mds1),
      mds2: toNumber(row?.mds2)
    }))
    .filter((row) => row.mds1 !== null && row.mds2 !== null);
  const mdsStress = toNumber(mds.stress);
  const groupBySource = (rows) => {
    const grouped = new Map();
    for (const row of rows) {
      const source = String(row?.source || "Unknown");
      if (!grouped.has(source)) {
        grouped.set(source, []);
      }
      grouped.get(source).push(row);
    }
    return Array.from(grouped.entries()).sort((a, b) => {
      const sizeDelta = b[1].length - a[1].length;
      if (sizeDelta !== 0) {
        return sizeDelta;
      }
      return String(a[0]).localeCompare(String(b[0]));
    });
  };
  const pcaGroupedRows = groupBySource(pcaArticleRows);
  const mdsGroupedRows = groupBySource(mdsArticleRows);
  const topDriverRows = drivers
    .map((row) => ({
      lens: String(row?.lens || ""),
      weightedContribution: toNumber(row?.weighted_contribution)
    }))
    .filter((row) => row.lens && row.weightedContribution !== null)
    .sort((a, b) => (b.weightedContribution || 0) - (a.weightedContribution || 0))
    .slice(0, 12);
  const topDriverTotal = topDriverRows.reduce((acc, row) => acc + (row.weightedContribution || 0), 0);
  const temporalVolumeByDay = {};
  for (const row of temporalPcaPointRows) {
    const key = String(row.dayIndex);
    temporalVolumeByDay[key] = (temporalVolumeByDay[key] || 0) + 1;
  }
  const temporalPcaDrift = temporalPcaCentroidRows.map((row, index) => {
    if (index === 0) {
      return 0;
    }
    const previous = temporalPcaCentroidRows[index - 1];
    const dx = (row.pc1 || 0) - (previous.pc1 || 0);
    const dy = (row.pc2 || 0) - (previous.pc2 || 0);
    return Math.sqrt(dx * dx + dy * dy);
  });
  const temporalMdsByDay = new Map(temporalMdsCentroidRows.map((row) => [row.dayIndex, row]));
  const temporalMdsDrift = temporalPcaCentroidRows.map((row, index) => {
    if (index === 0) {
      return 0;
    }
    const previousPca = temporalPcaCentroidRows[index - 1];
    const current = temporalMdsByDay.get(row.dayIndex);
    const previous = temporalMdsByDay.get(previousPca.dayIndex);
    if (!current || !previous) {
      return null;
    }
    const dx = (current.mds1 || 0) - (previous.mds1 || 0);
    const dy = (current.mds2 || 0) - (previous.mds2 || 0);
    return Math.sqrt(dx * dx + dy * dy);
  });

  return (
    <>
      <DataModeControls searchParams={searchParams} />
      <div className="panel">
        <h3>PCA Status</h3>
        <StatusBlock status={String(pca.status || "unavailable")} reason={String(pca.reason || "")} />
        <div className="stats-grid">
          <StatCard label="Articles" value={formatNumber(pca.n_articles)} />
          <StatCard label="Lenses" value={formatNumber(pca.n_lenses)} />
          <StatCard label="Components" value={formatNumber(asArray(pca.components).length)} />
          <StatCard label="Coverage Mode" value={pca.coverage_mode || "n/a"} />
        </div>
      </div>

      <div className="panel">
        <h3>PCA Visuals</h3>
        {explainedRows.length === 0 &&
        centroidRows.length === 0 &&
        pcaArticleRows.length === 0 &&
        mdsArticleRows.length === 0 ? (
          <EmptyState />
        ) : (
          <div>
            <div style={{ marginBottom: "12px" }}>
              <PlotlyChart
                data={[
                  {
                    type: "bar",
                    x: explainedRows.map((row) => row.component),
                    y: explainedRows.map((row) => (row.explained || 0) * 100),
                    name: "Explained %",
                    marker: { color: "#4fd1c5" }
                  },
                  {
                    type: "scatter",
                    mode: "lines+markers",
                    x: explainedRows.map((row) => row.component),
                    y: explainedRows.map((row) => (row.cumulative || 0) * 100),
                    name: "Cumulative %",
                    line: { color: "#7aa7ff" }
                  }
                ]}
                layout={{ title: "Explained Variance by Component", yaxis: { title: "Percent" } }}
              />
            </div>
            <div style={{ marginBottom: "12px" }}>
              <PlotlyChart
                data={[
                  ...pcaGroupedRows.map(([source, rows]) => ({
                    type: "scatter",
                    mode: "markers",
                    name: source,
                    x: rows.map((row) => row.pc1),
                    y: rows.map((row) => row.pc2),
                    text: rows.map((row) => row.title),
                    customdata: rows.map((row) => [row.source, row.strongestLens, row.publishedAt]),
                    hovertemplate:
                      "Title: %{text}<br>" +
                      "PC1: %{x:.3f}<br>" +
                      "PC2: %{y:.3f}<br>" +
                      "Source: %{customdata[0]}<br>" +
                      "Strongest Lens: %{customdata[1]}<br>" +
                      "Published: %{customdata[2]}<extra></extra>",
                    marker: { size: 8, opacity: 0.75 }
                  })),
                  ...(centroidRows.length > 0
                    ? [
                        {
                          type: "scatter",
                          mode: "markers+text",
                          name: "Source Centroids",
                          x: centroidRows.map((row) => row.pc1),
                          y: centroidRows.map((row) => row.pc2),
                          text: centroidRows.map((row) => row.source),
                          textposition: "top center",
                          hovertemplate: "Source: %{text}<br>PC1: %{x:.3f}<br>PC2: %{y:.3f}<extra></extra>",
                          marker: { symbol: "x", size: 12, color: "#111111" }
                        }
                      ]
                    : [])
                ]}
                layout={{ title: "Article Distribution in PC1/PC2 Space", xaxis: { title: "PC1" }, yaxis: { title: "PC2" } }}
              />
            </div>
            <div>
              <PlotlyChart
                data={[
                  ...mdsGroupedRows.map(([source, rows]) => ({
                    type: "scatter",
                    mode: "markers",
                    name: source,
                    x: rows.map((row) => row.mds1),
                    y: rows.map((row) => row.mds2),
                    text: rows.map((row) => row.title),
                    customdata: rows.map((row) => [row.source, row.strongestLens, row.publishedAt]),
                    hovertemplate:
                      "Title: %{text}<br>" +
                      "MDS1: %{x:.3f}<br>" +
                      "MDS2: %{y:.3f}<br>" +
                      "Source: %{customdata[0]}<br>" +
                      "Strongest Lens: %{customdata[1]}<br>" +
                      "Published: %{customdata[2]}<extra></extra>",
                    marker: { size: 8, opacity: 0.75 }
                  })),
                  ...(mdsCentroidRows.length > 0
                    ? [
                        {
                          type: "scatter",
                          mode: "markers+text",
                          name: "Source Centroids",
                          x: mdsCentroidRows.map((row) => row.mds1),
                          y: mdsCentroidRows.map((row) => row.mds2),
                          text: mdsCentroidRows.map((row) => row.source),
                          textposition: "top center",
                          hovertemplate: "Source: %{text}<br>MDS1: %{x:.3f}<br>MDS2: %{y:.3f}<extra></extra>",
                          marker: { symbol: "x", size: 12, color: "#111111" }
                        }
                      ]
                    : [])
                ]}
                layout={{
                  title: `Article Distribution in MDS1/MDS2 Space${mdsStress !== null ? ` (Stress: ${mdsStress.toFixed(3)})` : ""}`,
                  xaxis: { title: "MDS1" },
                  yaxis: { title: "MDS2" }
                }}
              />
            </div>
          </div>
        )}
      </div>

      <div className="panel">
        <h3>Temporal Lens Geometry</h3>
        {timeSeriesRows.length === 0 &&
        temporalPcaPointRows.length === 0 &&
        temporalMdsPointRows.length === 0 &&
        temporalPcaCentroidRows.length === 0 ? (
          <EmptyState />
        ) : (
          <>
            <div className="chart-grid">
              {timeSeriesRows.length > 0 ? (
                <PlotlyChart
                  data={timeSeriesRows.map((series) => ({
                    type: "scatter",
                    mode: "lines+markers",
                    name: series.lens,
                    x: series.points.map((point) => point.date),
                    y: series.points.map((point) => point.mean),
                    customdata: series.points.map((point) => [point.count, point.median, point.min, point.max]),
                    hovertemplate:
                      "Lens: " +
                      series.lens +
                      "<br>Date: %{x}<br>Mean: %{y:.2f}<br>N: %{customdata[0]}<br>" +
                      "Median: %{customdata[1]:.2f}<br>Min/Max: %{customdata[2]:.2f} / %{customdata[3]:.2f}<extra></extra>"
                  }))}
                  layout={{
                    title: "Lens Time Series (Daily Mean Percent)",
                    xaxis: { title: "Date (UTC)" },
                    yaxis: { title: "Lens Percent" }
                  }}
                />
              ) : null}
              {temporalPcaPointRows.length > 0 ? (
                <PlotlyChart
                  data={[
                    {
                      type: "scatter",
                      mode: "markers",
                      name: "Articles",
                      x: temporalPcaPointRows.map((row) => row.pc1),
                      y: temporalPcaPointRows.map((row) => row.pc2),
                      text: temporalPcaPointRows.map((row) => row.title),
                      customdata: temporalPcaPointRows.map((row) => [row.source, row.date, row.strongestLens]),
                      marker: {
                        size: 8,
                        opacity: 0.7,
                        color: temporalPcaPointRows.map((row) => row.dayIndex),
                        colorscale: "Viridis",
                        showscale: true,
                        colorbar: { title: "Day Index" }
                      },
                      hovertemplate:
                        "Title: %{text}<br>PC1: %{x:.3f}<br>PC2: %{y:.3f}<br>" +
                        "Source: %{customdata[0]}<br>Date: %{customdata[1]}<br>" +
                        "Strongest Lens: %{customdata[2]}<extra></extra>"
                    },
                    ...(temporalPcaCentroidRows.length > 0
                      ? [
                          {
                            type: "scatter",
                            mode: "lines+markers",
                            name: "Daily Centroid Path",
                            x: temporalPcaCentroidRows.map((row) => row.pc1),
                            y: temporalPcaCentroidRows.map((row) => row.pc2),
                            text: temporalPcaCentroidRows.map((row) => row.date),
                            marker: { size: 9, symbol: "diamond", color: "#111111" },
                            line: { width: 2, color: "#111111" },
                            hovertemplate: "Date: %{text}<br>PC1: %{x:.3f}<br>PC2: %{y:.3f}<extra></extra>"
                          }
                        ]
                      : [])
                  ]}
                  layout={{ title: "Temporal Trajectory in PC1/PC2", xaxis: { title: "PC1" }, yaxis: { title: "PC2" } }}
                />
              ) : null}
              {temporalMdsPointRows.length > 0 ? (
                <PlotlyChart
                  data={[
                    {
                      type: "scatter",
                      mode: "markers",
                      name: "Articles",
                      x: temporalMdsPointRows.map((row) => row.mds1),
                      y: temporalMdsPointRows.map((row) => row.mds2),
                      text: temporalMdsPointRows.map((row) => row.title),
                      customdata: temporalMdsPointRows.map((row) => [row.source, row.date, row.strongestLens]),
                      marker: {
                        size: 8,
                        opacity: 0.7,
                        color: temporalMdsPointRows.map((row) => row.dayIndex),
                        colorscale: "Plasma",
                        showscale: true,
                        colorbar: { title: "Day Index" }
                      },
                      hovertemplate:
                        "Title: %{text}<br>MDS1: %{x:.3f}<br>MDS2: %{y:.3f}<br>" +
                        "Source: %{customdata[0]}<br>Date: %{customdata[1]}<br>" +
                        "Strongest Lens: %{customdata[2]}<extra></extra>"
                    },
                    ...(temporalMdsCentroidRows.length > 0
                      ? [
                          {
                            type: "scatter",
                            mode: "lines+markers",
                            name: "Daily Centroid Path",
                            x: temporalMdsCentroidRows.map((row) => row.mds1),
                            y: temporalMdsCentroidRows.map((row) => row.mds2),
                            text: temporalMdsCentroidRows.map((row) => row.date),
                            marker: { size: 9, symbol: "diamond", color: "#111111" },
                            line: { width: 2, color: "#111111" },
                            hovertemplate: "Date: %{text}<br>MDS1: %{x:.3f}<br>MDS2: %{y:.3f}<extra></extra>"
                          }
                        ]
                      : [])
                  ]}
                  layout={{
                    title: "Temporal Trajectory in MDS1/MDS2",
                    xaxis: { title: "MDS1" },
                    yaxis: { title: "MDS2" }
                  }}
                />
              ) : null}
            </div>
            {temporalPcaCentroidRows.length > 0 ? (
              <PlotlyChart
                data={[
                  {
                    type: "bar",
                    x: temporalPcaCentroidRows.map((row) => row.date),
                    y: temporalPcaCentroidRows.map((row) => temporalVolumeByDay[String(row.dayIndex)] || 0),
                    name: "Article Count",
                    marker: { color: "#6c757d" },
                    opacity: 0.5,
                    hovertemplate: "Date: %{x}<br>Articles: %{y}<extra></extra>"
                  },
                  {
                    type: "scatter",
                    mode: "lines+markers",
                    x: temporalPcaCentroidRows.map((row) => row.date),
                    y: temporalPcaDrift,
                    name: "PCA Centroid Drift",
                    line: { width: 2, color: "#0d6efd" },
                    yaxis: "y2",
                    hovertemplate: "Date: %{x}<br>PCA drift: %{y:.4f}<extra></extra>"
                  },
                  ...(temporalMdsDrift.some((value) => value !== null)
                    ? [
                        {
                          type: "scatter",
                          mode: "lines+markers",
                          x: temporalPcaCentroidRows.map((row) => row.date),
                          y: temporalMdsDrift,
                          name: "MDS Centroid Drift",
                          line: { width: 2, color: "#198754", dash: "dot" },
                          yaxis: "y2",
                          hovertemplate: "Date: %{x}<br>MDS drift: %{y:.4f}<extra></extra>"
                        }
                      ]
                    : [])
                ]}
                layout={{
                  title: "Temporal Diagnostics: Volume and Drift",
                  xaxis: { title: "Date (UTC)" },
                  yaxis: { title: "Article Count", rangemode: "tozero" },
                  yaxis2: { title: "Centroid Drift", overlaying: "y", side: "right", rangemode: "tozero" }
                }}
              />
            ) : null}
          </>
        )}
      </div>

      <div className="panel">
        <h3>PCA Loadings and Variance Drivers</h3>
        {loadingComponents.length === 0 || loadingLenses.length === 0 || loadingMatrix.length === 0 ? (
          <EmptyState />
        ) : (
          <div className="chart-grid">
            <PlotlyChart
              data={[
                {
                  type: "heatmap",
                  x: loadingLenses,
                  y: loadingComponents,
                  z: loadingMatrix,
                  zmin: -maxAbsLoading,
                  zmax: maxAbsLoading,
                  zmid: 0,
                  colorscale: "RdBu",
                  colorbar: { title: "Loading" },
                  hovertemplate: "Component: %{y}<br>Lens: %{x}<br>Loading: %{z:.4f}<extra></extra>"
                }
              ]}
              layout={{ title: "PCA Component Loadings", xaxis: { title: "Lens" }, yaxis: { title: "Component" } }}
            />
            <PlotlyChart
              data={[
                {
                  type: "bar",
                  x: selectedLoadings.map((row) => row.lens),
                  y: selectedLoadings.map((row) => row.loading),
                  marker: {
                    color: selectedLoadings.map((row) => (row.loading >= 0 ? "#198754" : "#dc3545"))
                  },
                  hovertemplate: "Lens: %{x}<br>Loading: %{y:.4f}<extra></extra>"
                }
              ]}
              layout={{
                title: selectedComponent ? `Lens Loadings for ${selectedComponent}` : "Lens Loadings",
                xaxis: { title: "Lens" },
                yaxis: { title: "Loading" }
              }}
            />
            <PlotlyChart
              data={[
                {
                  type: "bar",
                  x: topDriverRows.map((row) => row.lens),
                  y: topDriverRows.map((row) =>
                    topDriverTotal > 0 ? ((row.weightedContribution || 0) / topDriverTotal) * 100 : 0
                  ),
                  marker: { color: "#fd7e14" },
                  hovertemplate: "Lens: %{x}<br>Weighted contribution: %{y:.2f}%<extra></extra>"
                }
              ]}
              layout={{ title: "Variance Drivers by Lens", xaxis: { title: "Lens" }, yaxis: { title: "Contribution %" } }}
            />
          </div>
        )}
      </div>

      <div className="panel">
        <h3>Explained Variance</h3>
        {explained.length === 0 ? (
          <EmptyState />
        ) : (
          <table className="news-table compact">
            <thead>
              <tr>
                <th>Component</th>
                <th>Eigenvalue</th>
                <th>Explained</th>
                <th>Cumulative</th>
              </tr>
            </thead>
            <tbody>
              {explained.map((row) => (
                <tr key={String(row.component)}>
                  <td>{row.component}</td>
                  <td>{formatDecimal(row.eigenvalue, 4)}</td>
                  <td>{formatPercent(row.explained_variance_ratio)}</td>
                  <td>{formatPercent(row.cumulative_variance_ratio)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      <div className="panel">
        <h3>Variance Drivers</h3>
        {drivers.length === 0 ? (
          <EmptyState />
        ) : (
          <table className="news-table compact">
            <thead>
              <tr>
                <th>Lens</th>
                <th>Weighted Contribution</th>
                <th>PC1</th>
                <th>PC2</th>
              </tr>
            </thead>
            <tbody>
              {drivers.slice(0, 20).map((row) => (
                <tr key={String(row.lens)}>
                  <td>{row.lens}</td>
                  <td>{formatDecimal(row.weighted_contribution, 4)}</td>
                  <td>{formatDecimal(row.pc1_loading, 4)}</td>
                  <td>{formatDecimal(row.pc2_loading, 4)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      <div className="panel">
        <h3>Component Interpretation</h3>
        {componentSummaryRows.length === 0 ? (
          <EmptyState />
        ) : (
          <table className="news-table compact">
            <thead>
              <tr>
                <th>Component</th>
                <th>Explained Variance</th>
                <th>Strongest Loadings</th>
                <th>Top Positive</th>
                <th>Top Negative</th>
              </tr>
            </thead>
            <tbody>
              {componentSummaryRows.map((row, index) => {
                const strongest = asArray(row?.strongest_loadings)
                  .slice(0, 3)
                  .map((entry) => `${String(entry?.lens || "n/a")} (${formatDecimal(entry?.loading, 3)})`)
                  .join(", ");
                const positive = asArray(row?.top_positive)
                  .slice(0, 3)
                  .map((entry) => `${String(entry?.lens || "n/a")} (${formatDecimal(entry?.loading, 3)})`)
                  .join(", ");
                const negative = asArray(row?.top_negative)
                  .slice(0, 3)
                  .map((entry) => `${String(entry?.lens || "n/a")} (${formatDecimal(entry?.loading, 3)})`)
                  .join(", ");
                return (
                  <tr key={`${row?.component || "component"}-${index}`}>
                    <td>{String(row?.component || "n/a")}</td>
                    <td>{formatPercent(row?.explained_variance_ratio)}</td>
                    <td>{strongest || "n/a"}</td>
                    <td>{positive || "n/a"}</td>
                    <td>{negative || "n/a"}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        )}
      </div>

      <div className="panel">
        <h3>Source Centroids</h3>
        {centroids.length === 0 ? (
          <EmptyState />
        ) : (
          <table className="news-table compact">
            <thead>
              <tr>
                <th>Source</th>
                <th>Count</th>
                <th>PC1</th>
                <th>PC2</th>
              </tr>
            </thead>
            <tbody>
              {centroids.slice(0, 25).map((row) => (
                <tr key={String(row.source || "unknown")}>
                  <td>{row.source || "Unknown"}</td>
                  <td>{formatNumber(row.count)}</td>
                  <td>{formatDecimal(row.pc1, 3)}</td>
                  <td>{formatDecimal(row.pc2, 3)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </>
  );
}

function SourceDifferentiationBlock({ title, differentiation, confounded = false, reliability }) {
  const data = asObject(differentiation);
  const multivariate = asObject(data.multivariate);
  const classification = asObject(data.classification);
  const reliabilityView = asObject(reliability);
  const reliabilityFlags = asArray(reliabilityView.flags);
  const reliabilityScore = toNumber(reliabilityView.score);
  const sourceCountRows = sourceCountsToRows(data.source_counts).slice(0, 20);
  const accuracy = toNumber(classification.accuracy);
  const baselineAccuracy = toNumber(classification.baseline_accuracy);
  const showAccuracyChart = accuracy !== null || baselineAccuracy !== null;
  return (
    <div className="panel">
      <h3>{title}</h3>
      {confounded ? <p className="muted">Label: topic-confounded</p> : null}
      <StatusBlock status={String(data.status || "unavailable")} reason={String(data.reason || "")} />
      <p className="muted">
        Scope status: {String(data.status || "unknown")}
        {reliabilityScore !== null
          ? ` | Reliability: ${String(reliabilityView.tier || "n/a")} (${reliabilityScore.toFixed(2)})`
          : ""}
        {reliabilityFlags.length > 0 ? ` | Reliability flags: ${formatNumber(reliabilityFlags.length)}` : ""}
      </p>
      <div className="stats-grid">
        <StatCard label="Articles" value={formatNumber(data.n_articles)} />
        <StatCard label="Sources" value={formatNumber(data.n_sources)} />
        <StatCard label="Lenses" value={formatNumber(data.n_lenses)} />
        <StatCard label="Permutations" value={formatNumber(data.permutations)} />
        <StatCard label="LOOCV Accuracy" value={formatPercent(classification.accuracy)} />
        <StatCard label="Baseline Accuracy" value={formatPercent(classification.baseline_accuracy)} />
      </div>
      {sourceCountRows.length > 0 || showAccuracyChart ? (
        <div className="chart-grid">
          {sourceCountRows.length > 0 ? (
            <PlotlyChart
              data={[
                {
                  type: "bar",
                  x: sourceCountRows.map((row) => row.source),
                  y: sourceCountRows.map((row) => row.count),
                  marker: { color: "#4fd1c5" }
                }
              ]}
              layout={{ title: "Source Counts in Analysis Slice", yaxis: { title: "Articles" } }}
            />
          ) : null}
          {showAccuracyChart ? (
            <PlotlyChart
              data={[
                {
                  type: "bar",
                  x: ["Classifier", "Baseline"],
                  y: [accuracy !== null ? accuracy * 100 : 0, baselineAccuracy !== null ? baselineAccuracy * 100 : 0],
                  marker: { color: ["#7aa7ff", "#fd7e14"] }
                }
              ]}
              layout={{ title: "Classification Accuracy vs Baseline", yaxis: { title: "Accuracy %", range: [0, 100] } }}
            />
          ) : null}
        </div>
      ) : null}
      <table className="news-table compact">
        <tbody>
          <tr>
            <th>Multivariate F</th>
            <td>{formatDecimal(multivariate.f_stat, 4)}</td>
          </tr>
          <tr>
            <th>Multivariate R²</th>
            <td>{formatDecimal(multivariate.r_squared, 4)}</td>
          </tr>
          <tr>
            <th>Between df</th>
            <td>{formatNumber(multivariate.df_between)}</td>
          </tr>
          <tr>
            <th>Within df</th>
            <td>{formatNumber(multivariate.df_within)}</td>
          </tr>
          <tr>
            <th>Multivariate p_perm</th>
            <td>{formatDecimal(multivariate.p_perm, 4)}</td>
          </tr>
          <tr>
            <th>LOOCV Accuracy</th>
            <td>{formatPercent(classification.accuracy)}</td>
          </tr>
          <tr>
            <th>Baseline Accuracy</th>
            <td>{formatPercent(classification.baseline_accuracy)}</td>
          </tr>
          <tr>
            <th>Evaluated</th>
            <td>{formatNumber(classification.evaluated)}</td>
          </tr>
          <tr>
            <th>Total</th>
            <td>{formatNumber(classification.total)}</td>
          </tr>
          <tr>
            <th>Classification p_perm</th>
            <td>{formatDecimal(classification.p_perm, 4)}</td>
          </tr>
        </tbody>
      </table>
    </div>
  );
}

async function renderSourceDifferentiation(searchParams) {
  const payload = await fetchStatsForMode(searchParams);
  const derived = getStatsDerived(payload);
  const pooled = asObject(derived.source_differentiation);
  const sourceReliability = asObject(derived.source_reliability);
  const topicControl = asObject(derived.source_topic_control);
  const topics = asArray(topicControl.topics);
  const mode = normalizeMode(searchParams);
  const dataMode = normalizeDataMode(searchParams);
  const snapshotDateValue = selectedSnapshotDateValue(searchParams);
  const selectedTopic = selectedTopicFromQuery(searchParams, topics);
  const selectedTopicName = selectedTopic ? String(selectedTopic.topic || "") : "";
  const selectedTopicDiff = asObject(selectedTopic?.source_differentiation);
  const selectedTopicReason = String(selectedTopicDiff.reason || "");
  const isTopicUnavailable = String(selectedTopicDiff.status || "") !== "ok";
  const reliabilityView = selectSourceReliabilityView(sourceReliability, mode, selectedTopicName);

  return (
    <>
      <DataModeControls searchParams={searchParams} extraParams={{ mode, topic: selectedTopicName }} />
      <div className="panel">
        <h3>Analysis Mode</h3>
        <div className="top-nav-links">
          <a
            className={`news-nav-link ${mode === "pooled" ? "active-link" : ""}`}
            href={analysisModeQueryHref("pooled", selectedTopicName, dataMode, snapshotDateValue)}
          >
            Pooled (topic-confounded)
          </a>
          <a
            className={`news-nav-link ${mode === "within-topic" ? "active-link" : ""}`}
            href={analysisModeQueryHref("within-topic", selectedTopicName, dataMode, snapshotDateValue)}
          >
            Within-topic
          </a>
        </div>
        {mode === "within-topic" && topics.length > 0 ? (
          <>
            <p className="muted" style={{ marginTop: "10px" }}>
              Topic slice
            </p>
            <div className="top-nav-links">
              {topics.slice(0, 24).map((topic) => {
                const topicName = String(topic?.topic || "Unknown");
                const selected = topicName === selectedTopicName;
                return (
                  <a
                    key={topicName}
                    className={`news-nav-link ${selected ? "active-link" : ""}`}
                    href={analysisModeQueryHref("within-topic", topicName, dataMode, snapshotDateValue)}
                  >
                    {topicName}
                  </a>
                );
              })}
            </div>
          </>
        ) : null}
      </div>

      {mode === "pooled" ? (
        <SourceDifferentiationBlock
          title="Pooled Source Differentiation"
          differentiation={pooled}
          confounded
          reliability={reliabilityView}
        />
      ) : selectedTopic ? (
        <SourceDifferentiationBlock
          title={`Within-Topic Source Differentiation: ${selectedTopicName}`}
          differentiation={selectedTopicDiff}
          reliability={reliabilityView}
        />
      ) : (
        <div className="panel">
          <h3>Within-Topic Source Differentiation</h3>
          <EmptyState />
        </div>
      )}

      <div className="panel">
        <h3>Topic Slice Overview</h3>
        {mode === "within-topic" && selectedTopic && isTopicUnavailable ? (
          <p className="muted">
            Selected topic is unavailable: {selectedTopicReason || "Insufficient data for this topic slice."}
          </p>
        ) : null}
        {topics.length === 0 ? (
          <EmptyState />
        ) : (
          <table className="news-table compact">
            <thead>
              <tr>
                <th>Topic</th>
                <th>Status</th>
                <th>Articles</th>
                <th>Sources</th>
                <th>F-stat</th>
                <th>LOOCV Acc</th>
              </tr>
            </thead>
            <tbody>
              {topics.map((topic) => {
                const diff = asObject(topic.source_differentiation);
                const multi = asObject(diff.multivariate);
                const cls = asObject(diff.classification);
                return (
                  <tr key={String(topic.topic || "unknown-topic")}>
                    <td>{topic.topic || "Unknown"}</td>
                    <td>{String(diff.status || "unavailable")}</td>
                    <td>{formatNumber(topic.n_articles)}</td>
                    <td>{formatNumber(topic.n_sources)}</td>
                    <td>{formatDecimal(multi.f_stat, 3)}</td>
                    <td>{formatPercent(cls.accuracy)}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        )}
      </div>
    </>
  );
}

function SourceEffectsBlock({ title, effects, confounded = false, maxLenses, qThreshold, selectedLens, reliability }) {
  const data = asObject(effects);
  const rows = asArray(data.rows);
  const filteredRows = rows
    .filter((row) => {
      if (qThreshold >= 1.0) {
        return true;
      }
      const pPermFdr = toNumber(row?.p_perm_fdr);
      const pPermRaw = toNumber(row?.p_perm_raw);
      const pPerm = toNumber(row?.p_perm);
      const candidate = pPermFdr !== null ? pPermFdr : pPermRaw !== null ? pPermRaw : pPerm;
      return candidate !== null && candidate <= qThreshold;
    })
    .slice(0, maxLenses);
  const selectedLensRow =
    filteredRows.find((row) => String(row?.lens || "") === selectedLens) || filteredRows[0] || null;
  const selectedLensName = selectedLensRow ? String(selectedLensRow?.lens || "") : "";
  const multipleTesting = asObject(data.multiple_testing);
  const reliabilityView = asObject(reliability);
  const reliabilityFlags = asArray(reliabilityView.flags);
  const etaRows = filteredRows
    .map((row) => ({
      lens: String(row?.lens || ""),
      etaSq: toNumber(row?.eta_sq),
      sourceMeans: asObject(row?.source_means)
    }))
    .filter((row) => row.lens && row.etaSq !== null);
  const focusLens = selectedLensName
    ? etaRows.find((row) => row.lens === selectedLensName) || etaRows[0]
    : etaRows[0];
  const focusLensMeanRows = focusLens
    ? Object.entries(focusLens.sourceMeans)
        .map(([source, mean]) => ({
          source: String(source || "Unknown"),
          mean: toNumber(mean)
        }))
        .filter((row) => row.mean !== null)
        .sort((a, b) => (b.mean || 0) - (a.mean || 0))
    : [];
  const bestQValue = Math.min(
    ...filteredRows
      .map((row) => toNumber(row?.p_perm_fdr))
      .filter((value) => value !== null)
      .map((value) => Number(value))
  );
  const bestRawPValue = Math.min(
    ...filteredRows
      .map((row) => toNumber(row?.p_perm_raw))
      .filter((value) => value !== null)
      .map((value) => Number(value))
  );
  const reliabilityScore = toNumber(reliabilityView.score);
  const thresholdLabel = qThreshold >= 1.0 ? "All" : formatDecimal(qThreshold, 2);
  return (
    <div className="panel">
      <h3>{title}</h3>
      {confounded ? <p className="muted">Label: topic-confounded</p> : null}
      <StatusBlock status={String(data.status || "unavailable")} reason={String(data.reason || "")} />
      <p className="muted">
        Rows shown: {formatNumber(filteredRows.length)} | q-threshold: {thresholdLabel}
        {reliabilityScore !== null
          ? ` | Reliability: ${String(reliabilityView.tier || "n/a")} (${reliabilityScore.toFixed(2)})`
          : ""}
        {reliabilityFlags.length > 0 ? ` | Reliability flags: ${formatNumber(reliabilityFlags.length)}` : ""}
      </p>
      <div className="stats-grid">
        <StatCard label="Rows" value={formatNumber(filteredRows.length)} />
        <StatCard label="Permutations" value={formatNumber(data.permutations)} />
        <StatCard label="Multiple Testing" value={multipleTesting.method || "n/a"} />
        <StatCard label="Tests" value={formatNumber(multipleTesting.n_tests)} />
        <StatCard label="Best q-value (FDR)" value={Number.isFinite(bestQValue) ? formatDecimal(bestQValue, 4) : "n/a"} />
        <StatCard
          label="Best raw p-value"
          value={Number.isFinite(bestRawPValue) ? formatDecimal(bestRawPValue, 4) : "n/a"}
        />
      </div>
      {etaRows.length > 0 ? (
        <div className="chart-grid">
          <PlotlyChart
            data={[
              {
                type: "bar",
                orientation: "h",
                y: etaRows.map((row) => row.lens).reverse(),
                x: etaRows.map((row) => row.etaSq || 0).reverse(),
                marker: { color: "#7aa7ff" }
              }
            ]}
            layout={{ title: "Lens Effect Size (eta squared)", xaxis: { title: "eta squared" } }}
          />
          <PlotlyChart
            data={[
              {
                type: "bar",
                x: focusLensMeanRows.map((row) => row.source),
                y: focusLensMeanRows.map((row) => row.mean || 0),
                marker: { color: "#fd7e14" }
              }
            ]}
            layout={{
              title: `Source Means for ${focusLens?.lens || "selected lens"}`,
              yaxis: { title: "Mean Lens Percent" }
            }}
          />
        </div>
      ) : null}
      {filteredRows.length === 0 ? (
        <EmptyState />
      ) : (
        <table className="news-table compact">
          <thead>
            <tr>
              <th>Lens</th>
              <th>n</th>
              <th>Sources</th>
              <th>F</th>
              <th>eta²</th>
              <th>p_perm_raw</th>
              <th>p_perm_fdr</th>
              <th>Source Gap</th>
              <th>Top / Bottom</th>
            </tr>
          </thead>
          <tbody>
            {filteredRows.map((row) => (
              <tr key={String(row.lens || "unknown-lens")}>
                <td>{row.lens || "Unknown"}</td>
                <td>{formatNumber(row.n)}</td>
                <td>{formatNumber(row.n_sources)}</td>
                <td>{formatDecimal(row.f_stat, 3)}</td>
                <td>{formatDecimal(row.eta_sq, 4)}</td>
                <td>{formatDecimal(row.p_perm_raw, 4)}</td>
                <td>{formatDecimal(row.p_perm_fdr, 4)}</td>
                <td>{formatDecimal(row.source_gap, 2)}</td>
                <td>
                  {row.top_source || "n/a"} / {row.bottom_source || "n/a"}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}

async function renderSourceEffects(searchParams) {
  const payload = await fetchStatsForMode(searchParams);
  const derived = getStatsDerived(payload);
  const pooled = asObject(derived.source_lens_effects);
  const sourceReliability = asObject(derived.source_reliability);
  const topicControl = asObject(derived.source_topic_control);
  const topics = asArray(topicControl.topics);
  const mode = normalizeMode(searchParams);
  const dataMode = normalizeDataMode(searchParams);
  const snapshotDateValue = selectedSnapshotDateValue(searchParams);
  const selectedTopic = selectedTopicFromQuery(searchParams, topics);
  const selectedTopicName = selectedTopic ? String(selectedTopic.topic || "") : "";
  const selectedTopicEffects = asObject(selectedTopic?.source_lens_effects);
  const selectedTopicReason = String(selectedTopicEffects.reason || "");
  const isTopicUnavailable = String(selectedTopicEffects.status || "") !== "ok";
  const reliabilityView = selectSourceReliabilityView(sourceReliability, mode, selectedTopicName);
  const { maxLenses, qThreshold } = normalizedSourceEffectsFilter(searchParams);
  const selectedLens = getQueryParam(searchParams, "lens");
  const sourceEffectsExtraParams = {
    max_lenses: maxLenses,
    q_threshold: qThreshold,
    lens: selectedLens
  };
  const activeEffects = mode === "pooled" ? pooled : selectedTopicEffects;
  const availableLensOptions = asArray(activeEffects.rows)
    .map((row) => String(row?.lens || "").trim())
    .filter((lens) => lens);
  const selectedLensValue = availableLensOptions.includes(selectedLens) ? selectedLens : availableLensOptions[0] || "";

  return (
    <>
      <DataModeControls
        searchParams={searchParams}
        extraParams={{ mode, topic: selectedTopicName, ...sourceEffectsExtraParams }}
      />
      <div className="panel">
        <h3>Analysis Mode</h3>
        <div className="top-nav-links">
          <a
            className={`news-nav-link ${mode === "pooled" ? "active-link" : ""}`}
            href={analysisModeQueryHref("pooled", selectedTopicName, dataMode, snapshotDateValue, sourceEffectsExtraParams)}
          >
            Pooled (topic-confounded)
          </a>
          <a
            className={`news-nav-link ${mode === "within-topic" ? "active-link" : ""}`}
            href={analysisModeQueryHref(
              "within-topic",
              selectedTopicName,
              dataMode,
              snapshotDateValue,
              sourceEffectsExtraParams
            )}
          >
            Within-topic
          </a>
        </div>
        {mode === "within-topic" && topics.length > 0 ? (
          <>
            <p className="muted" style={{ marginTop: "10px" }}>
              Topic slice
            </p>
            <div className="top-nav-links">
              {topics.slice(0, 24).map((topic) => {
                const topicName = String(topic?.topic || "Unknown");
                const selected = topicName === selectedTopicName;
                return (
                  <a
                    key={topicName}
                    className={`news-nav-link ${selected ? "active-link" : ""}`}
                    href={analysisModeQueryHref(
                      "within-topic",
                      topicName,
                      dataMode,
                      snapshotDateValue,
                      sourceEffectsExtraParams
                    )}
                  >
                    {topicName}
                  </a>
                );
              })}
            </div>
          </>
        ) : null}
      </div>
      <div className="panel">
        <h3>Effect Filters</h3>
        <form method="get" className="inline-form-grid">
          <input type="hidden" name="data_mode" value={dataMode} />
          <input type="hidden" name="snapshot" value={snapshotDateValue} />
          <input type="hidden" name="mode" value={mode} />
          <input type="hidden" name="topic" value={selectedTopicName} />
          <label className="muted" htmlFor="source-effects-max-lenses">
            Lenses shown
          </label>
          <select id="source-effects-max-lenses" name="max_lenses" defaultValue={String(maxLenses)}>
            {[5, 10, 15, 20].map((value) => (
              <option key={value} value={String(value)}>
                {value}
              </option>
            ))}
          </select>
          <label className="muted" htmlFor="source-effects-q-threshold">
            Max q-value (FDR)
          </label>
          <select id="source-effects-q-threshold" name="q_threshold" defaultValue={String(qThreshold)}>
            <option value="1">All</option>
            <option value="0.1">0.10</option>
            <option value="0.05">0.05</option>
            <option value="0.01">0.01</option>
          </select>
          <label className="muted" htmlFor="source-effects-lens">
            Lens detail
          </label>
          <select id="source-effects-lens" name="lens" defaultValue={selectedLensValue} disabled={availableLensOptions.length === 0}>
            {availableLensOptions.length === 0 ? (
              <option value="">No lens rows</option>
            ) : (
              availableLensOptions.slice(0, 50).map((lens) => (
                <option key={lens} value={lens}>
                  {lens}
                </option>
              ))
            )}
          </select>
          <div style={{ display: "flex", gap: "10px", alignItems: "center" }}>
            <button type="submit" className="news-nav-link active-link">
              Apply
            </button>
          </div>
        </form>
      </div>

      {mode === "pooled" ? (
        <SourceEffectsBlock
          title="Pooled Source Effects"
          effects={pooled}
          confounded
          maxLenses={maxLenses}
          qThreshold={qThreshold}
          selectedLens={selectedLensValue}
          reliability={reliabilityView}
        />
      ) : selectedTopic ? (
        <SourceEffectsBlock
          title={`Within-Topic Source Effects: ${selectedTopicName}`}
          effects={selectedTopicEffects}
          maxLenses={maxLenses}
          qThreshold={qThreshold}
          selectedLens={selectedLensValue}
          reliability={reliabilityView}
        />
      ) : (
        <div className="panel">
          <h3>Within-Topic Source Effects</h3>
          <EmptyState />
        </div>
      )}

      <div className="panel">
        <h3>Topic Slice Overview</h3>
        {mode === "within-topic" && selectedTopic && isTopicUnavailable ? (
          <p className="muted">
            Selected topic is unavailable: {selectedTopicReason || "Insufficient data for this topic slice."}
          </p>
        ) : null}
        {topics.length === 0 ? (
          <EmptyState />
        ) : (
          <table className="news-table compact">
            <thead>
              <tr>
                <th>Topic</th>
                <th>Status</th>
                <th>Lens Rows</th>
                <th>Best Lens</th>
                <th>Best eta²</th>
              </tr>
            </thead>
            <tbody>
              {topics.map((topic) => {
                const effects = asObject(topic.source_lens_effects);
                const rows = asArray(effects.rows);
                const best = rows.length > 0 ? rows[0] : null;
                return (
                  <tr key={String(topic.topic || "unknown-topic")}>
                    <td>{topic.topic || "Unknown"}</td>
                    <td>{String(effects.status || "unavailable")}</td>
                    <td>{formatNumber(rows.length)}</td>
                    <td>{best?.lens || "n/a"}</td>
                    <td>{formatDecimal(best?.eta_sq, 3)}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        )}
      </div>
    </>
  );
}

async function renderScoreLab(searchParams) {
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

async function renderLensExplorer(searchParams) {
  const payload = await fetchStatsForMode(searchParams);
  const derived = getStatsDerived(payload);
  const lensViews = asObject(derived.lens_views);
  const summary = asObject(lensViews.summary);
  const articleRows = asArray(lensViews.article_rows).slice(0, 40);
  const sourceRows = asArray(lensViews.source_rows).slice(0, 20);
  const dominantLensCounts = asArray(summary.dominant_lens_counts).slice(0, 12);
  const largestGapRows = articleRows
    .map((row) => ({
      title: truncateText(row?.title || "Untitled", 44),
      gap: toNumber(row?.gap_vs_runner_up)
    }))
    .filter((row) => row.gap !== null)
    .sort((a, b) => (b.gap || 0) - (a.gap || 0))
    .slice(0, 12);

  return (
    <>
      <DataModeControls searchParams={searchParams} />
      <div className="panel">
        <h3>Lens Explorer Summary</h3>
        <div className="stats-grid">
          <StatCard label="Coverage Mode" value={lensViews.coverage_mode || "n/a"} />
          <StatCard label="Articles with Lens Scores" value={formatNumber(summary.article_count)} />
          <StatCard label="Sources" value={formatNumber(summary.source_count)} />
          <StatCard label="Most Common Strongest Lens" value={summary.top_dominant_lens || "n/a"} />
        </div>
      </div>

      <div className="panel">
        <h3>Explorer Visuals</h3>
        {dominantLensCounts.length === 0 && largestGapRows.length === 0 ? (
          <EmptyState />
        ) : (
          <div className="chart-grid">
            <PlotlyChart
              data={[
                {
                  type: "bar",
                  x: dominantLensCounts.map((row) => String(row?.lens || "Unknown")),
                  y: dominantLensCounts.map((row) => toNumber(row?.count) || 0),
                  marker: { color: "#4fd1c5" }
                }
              ]}
              layout={{ title: "Strongest Lens Frequency", yaxis: { title: "Articles" } }}
            />
            <PlotlyChart
              data={[
                {
                  type: "bar",
                  x: largestGapRows.map((row) => row.title),
                  y: largestGapRows.map((row) => row.gap || 0),
                  marker: { color: "#7aa7ff" }
                }
              ]}
              layout={{ title: "Largest Strongest-vs-Runner-Up Gaps", yaxis: { title: "Gap" } }}
            />
          </div>
        )}
      </div>

      <div className="panel">
        <h3>Article Lens Rows</h3>
        {articleRows.length === 0 ? (
          <EmptyState />
        ) : (
          <table className="news-table compact">
            <thead>
              <tr>
                <th>Title</th>
                <th>Source</th>
                <th>Strongest Lens</th>
                <th>Strongest %</th>
                <th>Gap vs Runner-up</th>
              </tr>
            </thead>
            <tbody>
              {articleRows.map((row, index) => (
                <tr key={`${String(row.title || "untitled")}-${index}`}>
                  <td>{truncateText(row.title || "Untitled", 90)}</td>
                  <td>{row.source || "Unknown"}</td>
                  <td>{row.strongest_lens || "n/a"}</td>
                  <td>{formatAlreadyPercent(row.strongest_percent)}</td>
                  <td>{formatDecimal(row.gap_vs_runner_up, 1)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      <div className="panel">
        <h3>Source Lens Means</h3>
        {sourceRows.length === 0 ? (
          <EmptyState />
        ) : (
          <table className="news-table compact">
            <thead>
              <tr>
                <th>Source</th>
                <th>Articles</th>
                <th>Strongest Lens</th>
                <th>Strongest Gap</th>
              </tr>
            </thead>
            <tbody>
              {sourceRows.map((row) => (
                <tr key={String(row.source || "unknown")}>
                  <td>{row.source || "Unknown"}</td>
                  <td>{formatNumber(row.article_count)}</td>
                  <td>{row.strongest_lens || "n/a"}</td>
                  <td>{formatDecimal(row.strongest_gap, 1)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </>
  );
}

async function renderLensBySource(searchParams) {
  const payload = await fetchStatsForMode(searchParams);
  const derived = getStatsDerived(payload);
  const lensViews = asObject(derived.lens_views);
  const lensNames = asArray(lensViews.lens_names);
  const sourceRows = asArray(lensViews.source_rows).slice(0, 20);
  const summary = asObject(lensViews.summary);
  const sourceLensAverageRows = asArray(summary.source_lens_average_rows)
    .map((row) => ({
      lens: String(row?.lens || ""),
      mean: toNumber(row?.mean)
    }))
    .filter((row) => row.lens && row.mean !== null)
    .sort((a, b) => (b.mean || 0) - (a.mean || 0));
  const focusLens = sourceLensAverageRows[0]?.lens || lensNames[0] || null;
  const matrix = sourceRows.map((row) => {
    const means = asObject(row.lens_means);
    return lensNames.map((lens) => toNumber(means[lens]) || 0);
  });

  return (
    <>
      <DataModeControls searchParams={searchParams} />
      <div className="panel">
        <h3>Source x Lens Matrix</h3>
        <div className="stats-grid">
          <StatCard label="Sources" value={formatNumber(sourceRows.length)} />
          <StatCard label="Lenses" value={formatNumber(lensNames.length)} />
          <StatCard label="Coverage Mode" value={lensViews.coverage_mode || "n/a"} />
        </div>
      </div>

      <div className="panel">
        <h3>Lens-by-Source Visuals</h3>
        {sourceRows.length === 0 || lensNames.length === 0 ? (
          <EmptyState />
        ) : (
          <div className="chart-grid">
            <PlotlyChart
              data={[
                {
                  type: "heatmap",
                  x: lensNames,
                  y: sourceRows.map((row) => String(row.source || "Unknown")),
                  z: matrix,
                  colorscale: "Viridis"
                }
              ]}
              layout={{ title: "Source x Lens Mean Heatmap" }}
            />
            <PlotlyChart
              data={[
                {
                  type: "bar",
                  x: sourceRows.map((row) => String(row.source || "Unknown")),
                  y: sourceRows.map((row) => {
                    const means = asObject(row.lens_means);
                    return focusLens ? toNumber(means[focusLens]) || 0 : 0;
                  }),
                  marker: { color: "#fd7e14" }
                }
              ]}
              layout={{ title: `Source Comparison for Focus Lens: ${focusLens || "n/a"}`, yaxis: { title: "Percent" } }}
            />
          </div>
        )}
      </div>

      <div className="panel">
        <h3>Lens Means by Source</h3>
        {sourceRows.length === 0 || lensNames.length === 0 ? (
          <EmptyState />
        ) : (
          <div className="table-scroll">
            <table className="news-table compact">
              <thead>
                <tr>
                  <th>Source</th>
                  <th>Articles</th>
                  {lensNames.map((lens) => (
                    <th key={lens}>{lens}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {sourceRows.map((row) => {
                  const means = asObject(row.lens_means);
                  return (
                    <tr key={String(row.source || "unknown")}>
                      <td>{row.source || "Unknown"}</td>
                      <td>{formatNumber(row.article_count)}</td>
                      {lensNames.map((lens) => (
                        <td key={`${row.source}-${lens}`}>{formatAlreadyPercent(means[lens])}</td>
                      ))}
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </>
  );
}

async function renderLensStability(searchParams) {
  const payload = await fetchStatsForMode(searchParams);
  const derived = getStatsDerived(payload);
  const lensViews = asObject(derived.lens_views);
  const stabilityRows = asArray(lensViews.stability_rows);
  const summary = asObject(lensViews.summary);
  const metricOptions = {
    stddev: "Std Dev",
    cv_percent: "Coeff. of Variation",
    source_gap: "Source Mean Gap",
    range: "Value Range"
  };
  const metricParam = String(getQueryParam(searchParams, "metric") || "stddev");
  const metric = Object.prototype.hasOwnProperty.call(metricOptions, metricParam) ? metricParam : "stddev";
  const topN = queryLimit(searchParams, "top_n", 10, 3, 30);
  const rankedRows = [...stabilityRows]
    .map((row) => ({
      lens: String(row?.lens || "Unknown"),
      count: toNumber(row?.count),
      mean: toNumber(row?.mean),
      stddev: toNumber(row?.stddev),
      cvPercent: toNumber(row?.cv_percent),
      sourceGap: toNumber(row?.source_gap),
      range: toNumber(row?.range)
    }))
    .sort((a, b) => {
      const aValue = metric === "cv_percent" ? a.cvPercent : metric === "source_gap" ? a.sourceGap : metric === "range" ? a.range : a.stddev;
      const bValue = metric === "cv_percent" ? b.cvPercent : metric === "source_gap" ? b.sourceGap : metric === "range" ? b.range : b.stddev;
      return (bValue || 0) - (aValue || 0);
    });
  const topRankedRows = rankedRows.slice(0, topN);
  const scatterRows = stabilityRows
    .map((row) => ({
      lens: String(row?.lens || "Unknown"),
      mean: toNumber(row?.mean),
      stddev: toNumber(row?.stddev),
      sourceGap: toNumber(row?.source_gap) || 0,
      count: Math.max(6, Math.min(48, (toNumber(row?.count) || 0) * 1.5))
    }))
    .filter((row) => row.mean !== null && row.stddev !== null);
  const rankedMetricRows = topRankedRows
    .map((row) => {
      const value = metric === "cv_percent" ? row.cvPercent : metric === "source_gap" ? row.sourceGap : metric === "range" ? row.range : row.stddev;
      return {
        lens: row.lens,
        value
      };
    })
    .filter((row) => row.value !== null);
  const dataMode = normalizeDataMode(searchParams);
  const snapshotDateValue = selectedSnapshotDateValue(searchParams);

  return (
    <>
      <DataModeControls searchParams={searchParams} />
      <div className="panel">
        <h3>Stability Filters</h3>
        <form method="get" className="inline-form-grid">
          <input type="hidden" name="data_mode" value={dataMode} />
          <input type="hidden" name="snapshot" value={snapshotDateValue} />
          <label className="muted" htmlFor="lens-stability-metric">
            Ranking metric
          </label>
          <select id="lens-stability-metric" name="metric" defaultValue={metric}>
            {Object.entries(metricOptions).map(([value, label]) => (
              <option key={value} value={value}>
                {label}
              </option>
            ))}
          </select>
          <label className="muted" htmlFor="lens-stability-topn">
            Top N lenses
          </label>
          <input id="lens-stability-topn" name="top_n" type="number" min={3} max={30} step={1} defaultValue={topN} />
          <div style={{ display: "flex", alignItems: "end" }}>
            <button type="submit" className="news-nav-link active-link">
              Apply
            </button>
          </div>
        </form>
      </div>
      <div className="panel">
        <h3>Stability Summary</h3>
        <div className="stats-grid">
          <StatCard label="Lenses Analyzed" value={formatNumber(summary.stability_lens_count)} />
          <StatCard label="Avg Std Dev" value={formatDecimal(summary.stability_avg_stddev, 2)} />
          <StatCard label="Most Volatile Lens" value={summary.stability_top_lens || "n/a"} />
          <StatCard label="Total Samples" value={formatNumber(summary.stability_total_samples)} />
        </div>
      </div>

      <div className="panel">
        <h3>Stability Visuals</h3>
        {scatterRows.length === 0 && rankedMetricRows.length === 0 ? (
          <EmptyState />
        ) : (
          <div className="chart-grid">
            <PlotlyChart
              data={[
                {
                  type: "scatter",
                  mode: "markers+text",
                  x: scatterRows.map((row) => row.mean),
                  y: scatterRows.map((row) => row.stddev),
                  text: scatterRows.map((row) => row.lens),
                  textposition: "top center",
                  marker: {
                    color: scatterRows.map((row) => row.sourceGap),
                    colorscale: "Viridis",
                    showscale: true,
                    colorbar: { title: "Source Gap" },
                    size: scatterRows.map((row) => row.count)
                  }
                }
              ]}
              layout={{ title: "Lens Mean vs Std Dev", xaxis: { title: "Mean" }, yaxis: { title: "Std Dev" } }}
            />
            <PlotlyChart
              data={[
                {
                  type: "bar",
                  orientation: "h",
                  y: rankedMetricRows.map((row) => row.lens).reverse(),
                  x: rankedMetricRows.map((row) => row.value || 0).reverse(),
                  marker: { color: "#dc3545" }
                }
              ]}
              layout={{
                title: `Top Lenses by ${metricOptions[metric]}`,
                xaxis: { title: metricOptions[metric] }
              }}
            />
          </div>
        )}
      </div>

      <div className="panel">
        <h3>Lens Stability Table</h3>
        {topRankedRows.length === 0 ? (
          <EmptyState />
        ) : (
          <table className="news-table compact">
            <thead>
              <tr>
                <th>Lens</th>
                <th>Samples</th>
                <th>Mean</th>
                <th>Std Dev</th>
                <th>CV %</th>
                <th>Source Gap</th>
                <th>Range</th>
              </tr>
            </thead>
            <tbody>
              {topRankedRows.map((row) => (
                <tr key={String(row.lens || "unknown")}>
                  <td>{row.lens || "Unknown"}</td>
                  <td>{formatNumber(row.count)}</td>
                  <td>{formatDecimal(row.mean, 2)}</td>
                  <td>{formatDecimal(row.stddev, 2)}</td>
                  <td>{formatDecimal(row.cvPercent, 2)}</td>
                  <td>{formatDecimal(row.sourceGap, 2)}</td>
                  <td>{formatDecimal(row.range, 2)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </>
  );
}

async function renderScraped(searchParams) {
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

function extractSnapshotMetrics(payload) {
  const derived = getStatsDerived(payload);
  const sourceCounts = asArray(derived.source_counts);
  const tagCounts = asArray(derived.tag_counts);
  const dailyCounts = asArray(derived.daily_counts_utc);
  return {
    total_articles: toNumber(derived.total_articles),
    scored_articles: toNumber(derived.scored_articles),
    zero_score_articles: toNumber(derived.zero_score_articles),
    unscorable_articles: toNumber(derived.unscorable_articles),
    score_coverage_ratio_percent:
      toNumber(derived.score_coverage_ratio) !== null ? (toNumber(derived.score_coverage_ratio) || 0) * 100 : null,
    source_count: sourceCounts.length,
    tag_count: tagCounts.length,
    days_covered: dailyCounts.length
  };
}

function metricDelta(current, snapshot) {
  if (current === null || snapshot === null) {
    return "n/a";
  }
  const delta = current - snapshot;
  return Number.isInteger(delta) ? `${delta >= 0 ? "+" : ""}${delta}` : `${delta >= 0 ? "+" : ""}${delta.toFixed(1)}`;
}

function pairKey(a, b) {
  return `${String(a || "")}\u0000${String(b || "")}`;
}

async function renderSnapshotCompare(searchParams) {
  const snapshotDate = snapshotDateFromSearchParams(searchParams);
  const snapshotInputValue = selectedSnapshotDateValue(searchParams);
  const forceRefresh = isTruthyQueryValue(getQueryParam(searchParams, "refresh"));
  const refreshHref = buildQueryHref({ snapshot: snapshotInputValue, refresh: "1" });
  const applyHref = buildQueryHref({ snapshot: snapshotInputValue, refresh: "" });
  if (!snapshotDate) {
    return (
      <>
        <div className="panel">
          <h3>Snapshot Compare Controls</h3>
          <form method="get" className="news-filter-grid">
            <label className="muted">
              Snapshot date (UTC)
              <input name="snapshot" type="date" defaultValue={snapshotInputValue} />
            </label>
            <div style={{ display: "flex", alignItems: "end", gap: "10px" }}>
              <button type="submit" className="news-nav-link">
                Run Compare
              </button>
            </div>
          </form>
        </div>
        <div className="panel">
          <h3>Snapshot Compare</h3>
          <p className="muted">Select a snapshot date to compare current vs historical metrics.</p>
        </div>
      </>
    );
  }

  const [currentPayload, snapshotPayload] = await Promise.all([
    fetchNewsJson(`/api/news/stats${forceRefresh ? "?refresh=true" : ""}`, forceRefresh ? { cache: "no-store" } : {}),
    fetchNewsJson(
      `/api/news/stats?snapshot_date=${encodeURIComponent(snapshotDate)}${forceRefresh ? "&refresh=true" : ""}`,
      forceRefresh ? { cache: "no-store" } : {}
    )
  ]);
  const currentMetrics = extractSnapshotMetrics(currentPayload);
  const snapshotMetrics = extractSnapshotMetrics(snapshotPayload);
  const currentMeta = asObject(currentPayload?.meta);
  const snapshotMeta = asObject(snapshotPayload?.meta);
  const rows = [
    ["Total Articles", "total_articles"],
    ["Scored Articles", "scored_articles"],
    ["Zero Scores", "zero_score_articles"],
    ["Unscorable", "unscorable_articles"],
    ["Score Coverage %", "score_coverage_ratio_percent"],
    ["Source Count", "source_count"],
    ["Tag Count", "tag_count"],
    ["Days Covered", "days_covered"]
  ];
  const chartRows = rows
    .map(([label, key]) => ({
      label,
      current: toNumber(currentMetrics[key]),
      snapshot: toNumber(snapshotMetrics[key])
    }))
    .filter((row) => row.current !== null && row.snapshot !== null);

  return (
    <>
      <div className="panel">
        <h3>Snapshot Compare Controls</h3>
        <form method="get" className="news-filter-grid">
          <label className="muted">
            Snapshot date (UTC)
            <input name="snapshot" type="date" defaultValue={snapshotDate} />
          </label>
          <div style={{ display: "flex", alignItems: "end", gap: "10px" }}>
            <button type="submit" className="news-nav-link">
              Run Compare
            </button>
            <a href={refreshHref} className="news-nav-link">
              Refresh
            </a>
          </div>
        </form>
        <p className="muted" style={{ marginTop: "10px" }}>
          Current generated: <strong>{currentMeta.generated_at || "n/a"}</strong> | Snapshot generated:{" "}
          <strong>{snapshotMeta.generated_at || "n/a"}</strong> | <a href={applyHref}>Clear refresh flag</a>
        </p>
      </div>
      <div className="panel">
        <h3>Snapshot Comparison Visual</h3>
        {chartRows.length === 0 ? (
          <EmptyState />
        ) : (
          <PlotlyChart
            data={[
              {
                type: "bar",
                name: "Current",
                x: chartRows.map((row) => row.label),
                y: chartRows.map((row) => row.current || 0),
                marker: { color: "#4fd1c5" }
              },
              {
                type: "bar",
                name: `Snapshot (${snapshotDate})`,
                x: chartRows.map((row) => row.label),
                y: chartRows.map((row) => row.snapshot || 0),
                marker: { color: "#7aa7ff" }
              }
            ]}
            layout={{ title: `Current vs Snapshot (${snapshotDate})`, barmode: "group", yaxis: { title: "Value" } }}
          />
        )}
      </div>
      <div className="panel">
        <h3>Current vs Snapshot ({snapshotDate})</h3>
        <table className="news-table compact">
          <thead>
            <tr>
              <th>Metric</th>
              <th>Current</th>
              <th>Snapshot</th>
              <th>Delta</th>
            </tr>
          </thead>
          <tbody>
            {rows.map(([label, key]) => (
              <tr key={key}>
                <td>{label}</td>
                <td>{formatDecimal(currentMetrics[key], key.includes("ratio") ? 1 : 0)}</td>
                <td>{formatDecimal(snapshotMetrics[key], key.includes("ratio") ? 1 : 0)}</td>
                <td>{metricDelta(currentMetrics[key], snapshotMetrics[key])}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </>
  );
}

function renderPlaceholder(title) {
  return (
    <div className="panel">
      <h3>Migration In Progress</h3>
      <p className="muted">
        {title} is routed and ready, but the full interactive port is still pending. This page will be migrated in a
        later pass while keeping existing Dash behavior intact.
      </p>
    </div>
  );
}

async function renderPageBody(slug, title, searchParams) {
  if (slug === "digest") {
    return renderDigest(searchParams);
  }
  if (slug === "stats") {
    return renderStats(searchParams);
  }
  if (slug === "sources") {
    return renderSources(searchParams);
  }
  if (slug === "lenses") {
    return renderLenses(searchParams);
  }
  if (slug === "lens-matrix") {
    return renderLensMatrix(searchParams);
  }
  if (slug === "lens-correlations") {
    return renderLensCorrelations(searchParams);
  }
  if (slug === "lens-pca") {
    return renderLensPca(searchParams);
  }
  if (slug === "source-differentiation") {
    return renderSourceDifferentiation(searchParams);
  }
  if (slug === "source-effects") {
    return renderSourceEffects(searchParams);
  }
  if (slug === "score-lab") {
    return renderScoreLab(searchParams);
  }
  if (slug === "lens-explorer") {
    return renderLensExplorer(searchParams);
  }
  if (slug === "lens-by-source") {
    return renderLensBySource(searchParams);
  }
  if (slug === "lens-stability") {
    return renderLensStability(searchParams);
  }
  if (slug === "tags") {
    return renderTags(searchParams);
  }
  if (slug === "source-tag-matrix") {
    return renderSourceTagMatrix(searchParams);
  }
  if (slug === "trends") {
    return renderTrends(searchParams);
  }
  if (slug === "scraped") {
    return renderScraped(searchParams);
  }
  if (slug === "snapshot-compare") {
    return renderSnapshotCompare(searchParams);
  }
  if (slug === "data-quality") {
    return renderDataQuality(searchParams);
  }
  if (slug === "workflow-status") {
    return renderWorkflowStatus(searchParams);
  }
  if (slug === "raw-json") {
    return renderRawJson(searchParams);
  }
  if (slug === "integration") {
    return renderIntegration(searchParams);
  }
  return renderPlaceholder(title);
}

export default async function NewsDetailPage({ params, searchParams }) {
  const page = getNewsPage(params.slug);
  if (!page) {
    notFound();
  }

  let body = null;
  let errorMessage = null;
  try {
    body = await renderPageBody(page.slug, page.title, searchParams);
  } catch (error) {
    errorMessage = error instanceof Error ? error.message : String(error);
  }

  return (
    <>
      <div className="page-title-row">
        <h2>{page.title}</h2>
        <p className="muted">Live FastAPI data</p>
      </div>
      <PageIntro summary={page.summary} />

      {errorMessage ? (
        <div className="panel">
          <h3>API Error</h3>
          <p className="muted">{errorMessage}</p>
          <p>
            Ensure FastAPI is running: <code>uvicorn src.api.fastapi_app:app --reload --port 9000</code>
          </p>
        </div>
      ) : (
        body
      )}
    </>
  );
}
