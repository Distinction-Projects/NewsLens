import {
  analysisModeQueryHref,
  asArray,
  asObject,
  fetchStatsForMode,
  formatDecimal,
  formatNumber,
  formatPercent,
  getStatsDerived,
  normalizeDataMode,
  normalizeMode,
  selectSourceReliabilityView,
  selectedSnapshotDateValue,
  selectedTopicFromQuery
} from "../../../../lib/newsPageUtils";
import { DataModeControls, EmptyState } from "../../../../components/news/NewsDashboardPrimitives";
import { SourceDifferentiationBlock } from "../../../../components/news/SourceAnalysisBlocks";

export async function render(searchParams) {
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
