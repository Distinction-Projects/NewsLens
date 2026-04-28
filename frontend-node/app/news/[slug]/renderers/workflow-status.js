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
