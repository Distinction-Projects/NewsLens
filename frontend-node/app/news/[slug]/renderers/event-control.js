import {
  asArray,
  asObject,
  fetchStatsForMode,
  formatDecimal,
  formatNumber,
  formatPercent,
  getQueryParam,
  getStatsDerived,
  queryLimit,
  truncateText
} from "../../../../lib/newsPageUtils";
import PlotlyChart from "../../../../components/PlotlyChart";
import { DataModeControls, EmptyState, StatCard, StatusBlock, StatusPill } from "../../../../components/news/NewsDashboardPrimitives";
import { SourceDifferentiationBlock, SourceEffectsBlock } from "../../../../components/news/SourceAnalysisBlocks";

function topRows(rows, limit) {
  return asArray(rows).slice(0, limit);
}

function JsonDownloadLinks() {
  const artifacts = [
    ["event_control_summary", "Summary"],
    ["event_clusters", "Clusters"],
    ["event_source_coverage", "Source coverage"],
    ["event_source_pair_coverage", "Pair coverage"],
    ["same_event_source_differentiation_summary", "Same-event source differentiation"],
    ["same_event_source_lens_effects", "Same-event source effects"],
    ["same_event_pairwise_source_lens_deltas", "Pairwise deltas"],
    ["same_event_variance_decomposition", "Variance decomposition"]
  ];
  return (
    <div className="top-nav-links">
      {artifacts.map(([artifact, label]) => (
        <a key={artifact} className="news-nav-link" href={`/api/news/export?artifact=${artifact}&format=json`}>
          {label} JSON
        </a>
      ))}
    </div>
  );
}

function ConfigTable({ config, cache }) {
  return (
    <table className="news-table compact">
      <tbody>
        <tr>
          <th>Embedding model</th>
          <td>{config.embedding_model || "n/a"}</td>
        </tr>
        <tr>
          <th>Dimensions</th>
          <td>{formatNumber(config.embedding_dimensions)}</td>
        </tr>
        <tr>
          <th>Similarity threshold</th>
          <td>{formatDecimal(config.similarity_threshold, 3)}</td>
        </tr>
        <tr>
          <th>Date window</th>
          <td>{formatNumber(config.date_window_days)} days</td>
        </tr>
        <tr>
          <th>Cache</th>
          <td>
            {cache.enabled ? "enabled" : "disabled"}; hits {formatNumber(cache.hits)}, misses {formatNumber(cache.misses)}, stored{" "}
            {formatNumber(cache.stored)}
          </td>
        </tr>
      </tbody>
    </table>
  );
}

function CoverageSection({ coverage, limit }) {
  const sourceRows = topRows(coverage.source_rows, limit);
  const pairRows = topRows(coverage.source_pair_rows, limit);
  return (
    <>
      <div className="panel">
        <h3>Event Coverage by Source</h3>
        <p className="muted">
          Use this before interpreting event-controlled effects. Low multi-source coverage means weak same-story comparison support.
        </p>
        {sourceRows.length === 0 ? (
          <EmptyState>No source coverage rows yet. Event matching may be unavailable or no multi-source clusters were found.</EmptyState>
        ) : (
          <>
            <PlotlyChart
              data={[
                {
                  type: "bar",
                  x: sourceRows.map((row) => String(row.source || "Unknown")),
                  y: sourceRows.map((row) => Number(row.multi_source_event_count) || 0),
                  marker: { color: "#4fd1c5" }
                }
              ]}
              layout={{ title: "Multi-Source Event Coverage by Source", yaxis: { title: "Events" } }}
            />
            <table className="news-table compact">
              <thead>
                <tr>
                  <th>Source</th>
                  <th>Total Scored</th>
                  <th>Events</th>
                  <th>Multi-Source Events</th>
                  <th>Multi-Source Article Coverage</th>
                </tr>
              </thead>
              <tbody>
                {sourceRows.map((row) => (
                  <tr key={String(row.source || "unknown")}>
                    <td>{row.source || "Unknown"}</td>
                    <td>{formatNumber(row.total_scored_articles)}</td>
                    <td>{formatNumber(row.event_count)}</td>
                    <td>{formatNumber(row.multi_source_event_count)}</td>
                    <td>{formatPercent(row.multi_source_event_article_coverage_ratio)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </>
        )}
      </div>

      <div className="panel">
        <h3>Source-Pair Event Overlap</h3>
        {pairRows.length === 0 ? (
          <EmptyState>No source-pair event overlap available.</EmptyState>
        ) : (
          <table className="news-table compact">
            <thead>
              <tr>
                <th>Source A</th>
                <th>Source B</th>
                <th>Shared Events</th>
                <th>Shared Event Articles</th>
                <th>Example Event IDs</th>
              </tr>
            </thead>
            <tbody>
              {pairRows.map((row) => (
                <tr key={`${row.source_a || "a"}-${row.source_b || "b"}`}>
                  <td>{row.source_a || "Unknown"}</td>
                  <td>{row.source_b || "Unknown"}</td>
                  <td>{formatNumber(row.shared_event_count)}</td>
                  <td>{formatNumber(row.shared_event_article_count)}</td>
                  <td>{asArray(row.event_ids).slice(0, 3).join(", ") || "n/a"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </>
  );
}

function EventClustersSection({ events, limit }) {
  const rows = topRows(events, limit);
  return (
    <div className="panel">
      <h3>Matched Event Clusters</h3>
      {rows.length === 0 ? (
        <EmptyState>No event clusters available.</EmptyState>
      ) : (
        <table className="news-table compact">
          <thead>
            <tr>
              <th>Event ID</th>
              <th>Representative Title</th>
              <th>Dates</th>
              <th>Articles</th>
              <th>Sources</th>
              <th>Top Topics</th>
              <th>Top Tags</th>
              <th>Article IDs</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((event) => {
              const sourceCounts = asObject(event.source_counts);
              const topicCounts = asObject(event.topic_counts);
              const tagCounts = asObject(event.tag_counts);
              const articleIds = asArray(event.article_ids).map((id) => String(id || "")).filter(Boolean);
              return (
                <tr key={String(event.event_id || event.representative_title)}>
                  <td>{event.event_id || "n/a"}</td>
                  <td>{truncateText(event.representative_title || "Untitled event", 90)}</td>
                  <td>
                    {event.date_start || "n/a"} to {event.date_end || "n/a"}
                  </td>
                  <td>{formatNumber(event.article_count)}</td>
                  <td>
                    {Object.entries(sourceCounts)
                      .slice(0, 4)
                      .map(([source, count]) => `${source} (${count})`)
                      .join(", ") || "n/a"}
                  </td>
                  <td>
                    {Object.entries(topicCounts)
                      .slice(0, 3)
                      .map(([topic, count]) => `${topic} (${count})`)
                      .join(", ") || "n/a"}
                  </td>
                  <td>
                    {Object.entries(tagCounts)
                      .slice(0, 5)
                      .map(([tag, count]) => `${tag} (${count})`)
                      .join(", ") || "n/a"}
                  </td>
                  <td>{articleIds.slice(0, 8).join(", ") || "n/a"}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      )}
    </div>
  );
}

function PairwiseDeltasSection({ deltas, limit }) {
  const rows = topRows(deltas.rows, limit);
  return (
    <div className="panel">
      <h3>Same-Event Pairwise Source Deltas</h3>
      <p className="muted">
        Positive delta means Source A scores higher than Source B on that lens within matched event coverage.
      </p>
      {rows.length === 0 ? (
        <EmptyState>No pairwise source/lens deltas available.</EmptyState>
      ) : (
        <table className="news-table compact">
          <thead>
            <tr>
              <th>Source A</th>
              <th>Source B</th>
              <th>Lens</th>
              <th>Events</th>
              <th>Mean Delta A-B</th>
              <th>Mean Abs Delta</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => (
              <tr key={`${row.source_a}-${row.source_b}-${row.lens}`}>
                <td>{row.source_a || "Unknown"}</td>
                <td>{row.source_b || "Unknown"}</td>
                <td>{row.lens || "Unknown"}</td>
                <td>{formatNumber(row.n_events)}</td>
                <td>{formatDecimal(row.mean_delta_a_minus_b, 2)}</td>
                <td>{formatDecimal(row.mean_abs_delta, 2)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}

function VarianceSection({ variance, limit }) {
  const rows = topRows(variance.rows, limit);
  return (
    <div className="panel">
      <h3>Event vs Source Variance Decomposition</h3>
      <p className="muted">
        This separates story/event variance from remaining source variance after event-centering.
      </p>
      {rows.length === 0 ? (
        <EmptyState>No variance decomposition rows available.</EmptyState>
      ) : (
        <>
          <PlotlyChart
            data={[
              {
                type: "bar",
                name: "Event eta squared",
                x: rows.map((row) => String(row.lens || "Unknown")),
                y: rows.map((row) => Number(row.event_eta_sq) || 0),
                marker: { color: "#7aa7ff" }
              },
              {
                type: "bar",
                name: "Source eta squared after event control",
                x: rows.map((row) => String(row.lens || "Unknown")),
                y: rows.map((row) => Number(row.source_eta_sq_event_centered) || 0),
                marker: { color: "#fd7e14" }
              }
            ]}
            layout={{ title: "Variance Share by Lens", barmode: "group", yaxis: { title: "Eta squared", range: [0, 1] } }}
          />
          <table className="news-table compact">
            <thead>
              <tr>
                <th>Lens</th>
                <th>N</th>
                <th>Events</th>
                <th>Sources</th>
                <th>Event eta²</th>
                <th>Source eta² After Event Control</th>
                <th>Strongest Residual Source</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((row) => (
                <tr key={String(row.lens || "unknown-lens")}>
                  <td>{row.lens || "Unknown"}</td>
                  <td>{formatNumber(row.n)}</td>
                  <td>{formatNumber(row.event_count)}</td>
                  <td>{formatNumber(row.source_count)}</td>
                  <td>{formatDecimal(row.event_eta_sq, 3)}</td>
                  <td>{formatDecimal(row.source_eta_sq_event_centered, 3)}</td>
                  <td>{row.strongest_source_after_event_control || "n/a"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </>
      )}
    </div>
  );
}

export async function render(searchParams) {
  const payload = await fetchStatsForMode(searchParams);
  const derived = getStatsDerived(payload);
  const eventControl = asObject(derived.event_control);
  const summary = asObject(eventControl.summary);
  const config = asObject(eventControl.config);
  const cache = asObject(eventControl.cache);
  const coverage = asObject(eventControl.event_coverage);
  const sameEventSourceDifferentiation = asObject(eventControl.same_event_source_differentiation);
  const sameEventSourceEffects = asObject(eventControl.same_event_source_lens_effects);
  const deltas = asObject(eventControl.same_event_pairwise_source_lens_deltas);
  const variance = asObject(eventControl.same_event_variance_decomposition);
  const limit = queryLimit(searchParams, "limit", 12, 5, 100);
  const maxLenses = queryLimit(searchParams, "max_lenses", 10, 3, 50);
  const qThresholdRaw = Number(getQueryParam(searchParams, "q_threshold"));
  const qThreshold = Number.isFinite(qThresholdRaw) ? Math.max(0, Math.min(1, qThresholdRaw)) : 1;
  const selectedLensValue = getQueryParam(searchParams, "lens");
  const effectRows = asArray(sameEventSourceEffects.rows);
  const availableLensOptions = effectRows.map((row) => String(row?.lens || "")).filter(Boolean);
  const selectedLens =
    selectedLensValue && availableLensOptions.includes(selectedLensValue)
      ? selectedLensValue
      : availableLensOptions[0] || "";

  return (
    <>
      <DataModeControls searchParams={searchParams} extraParams={{ limit }} />
      <div className="panel">
        <h3>Event-Control Status</h3>
        <StatusBlock status={eventControl.status} reason={eventControl.reason} />
        <p className="muted">
          Event control clusters articles by embedding similarity and publish-date proximity, then restricts source comparisons to
          matched same-story coverage.
        </p>
        <div className="stats-grid">
          <StatCard label="Articles Considered" value={formatNumber(summary.total_articles_considered)} />
          <StatCard label="Embedded Articles" value={formatNumber(summary.embedded_count)} />
          <StatCard label="Events" value={formatNumber(summary.event_count)} />
          <StatCard label="Multi-Source Events" value={formatNumber(summary.multi_source_event_count)} />
          <StatCard label="Singletons" value={formatNumber(summary.singleton_count)} />
          <StatCard label="Status" value={<StatusPill tone={eventControl.status === "ok" ? "good" : "bad"}>{eventControl.status || "unknown"}</StatusPill>} />
        </div>
        <ConfigTable config={config} cache={cache} />
      </div>

      <div className="panel">
        <h3>Display Controls and Exports</h3>
        <form method="get" className="inline-form-grid">
          <label className="muted" htmlFor="event-control-limit">
            Rows shown per table
          </label>
          <select id="event-control-limit" name="limit" defaultValue={String(limit)}>
            {[12, 25, 50, 100].map((value) => (
              <option key={value} value={String(value)}>
                {value}
              </option>
            ))}
          </select>
          <label className="muted" htmlFor="event-control-max-lenses">
            Lenses shown
          </label>
          <select id="event-control-max-lenses" name="max_lenses" defaultValue={String(maxLenses)}>
            {[5, 10, 15, 20, 50].map((value) => (
              <option key={value} value={String(value)}>
                {value}
              </option>
            ))}
          </select>
          <label className="muted" htmlFor="event-control-q-threshold">
            Max q-value (FDR)
          </label>
          <select id="event-control-q-threshold" name="q_threshold" defaultValue={String(qThreshold)}>
            <option value="1">All</option>
            <option value="0.1">0.10</option>
            <option value="0.05">0.05</option>
            <option value="0.01">0.01</option>
          </select>
          <label className="muted" htmlFor="event-control-lens">
            Lens detail
          </label>
          <select id="event-control-lens" name="lens" defaultValue={selectedLens} disabled={availableLensOptions.length === 0}>
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
          <button type="submit" className="news-nav-link active-link">
            Apply
          </button>
        </form>
        <p className="muted">Direct backend exports for event-control diagnostics.</p>
        <JsonDownloadLinks />
      </div>

      <CoverageSection coverage={coverage} limit={limit} />
      <SourceDifferentiationBlock
        title="Same-Event Source Differentiation"
        differentiation={sameEventSourceDifferentiation}
      />
      <SourceEffectsBlock
        title="Same-Event Source Effects"
        effects={sameEventSourceEffects}
        maxLenses={maxLenses}
        qThreshold={qThreshold}
        selectedLens={selectedLens}
      />
      <EventClustersSection events={eventControl.events} limit={limit} />
      <PairwiseDeltasSection deltas={deltas} limit={limit} />
      <VarianceSection variance={variance} limit={limit} />
    </>
  );
}
