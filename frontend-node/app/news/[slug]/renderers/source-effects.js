import {
  analysisModeQueryHref,
  asArray,
  asObject,
  fetchStatsForMode,
  formatDecimal,
  formatNumber,
  getQueryParam,
  getStatsDerived,
  normalizeDataMode,
  normalizeMode,
  selectSourceReliabilityView,
  selectedSnapshotDateValue,
  selectedTopicFromQuery
} from "../../../../lib/newsPageUtils";
import { DataModeControls, EmptyState } from "../../../../components/news/NewsDashboardPrimitives";
import { SourceEffectsBlock } from "../../../../components/news/SourceAnalysisBlocks";
import { normalizedSourceEffectsFilter } from "./shared";

export async function render(searchParams) {
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
