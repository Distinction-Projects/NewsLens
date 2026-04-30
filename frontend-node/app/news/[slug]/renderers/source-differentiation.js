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
  selectedTagSliceFromQuery,
  selectedTopicFromQuery
} from "../../../../lib/newsPageUtils";
import { DataModeControls, EmptyState, SectionHeader } from "../../../../components/news/NewsDashboardPrimitives";
import { SourceDifferentiationBlock, SourceReliabilityBlock } from "../../../../components/news/SourceAnalysisBlocks";

export async function render(searchParams) {
  const payload = await fetchStatsForMode(searchParams);
  const derived = getStatsDerived(payload);
  const pooled = asObject(derived.source_differentiation);
  const sourceReliability = asObject(derived.source_reliability);
  const topicControl = asObject(derived.source_topic_control);
  const tagSlicedAnalysis = asObject(derived.tag_sliced_analysis);
  const topics = asArray(topicControl.topics);
  const tagSlices = asArray(tagSlicedAnalysis.tags);
  const mode = normalizeMode(searchParams);
  const dataMode = normalizeDataMode(searchParams);
  const snapshotDateValue = selectedSnapshotDateValue(searchParams);
  const selectedTopic = selectedTopicFromQuery(searchParams, topics);
  const selectedTopicName = selectedTopic ? String(selectedTopic.topic || "") : "";
  const selectedTagSlice = selectedTagSliceFromQuery(searchParams, tagSlices);
  const selectedTagName = selectedTagSlice ? String(selectedTagSlice.tag || "") : "";
  const selectedTopicDiff = asObject(selectedTopic?.source_differentiation);
  const selectedTagDiff = asObject(selectedTagSlice?.source_differentiation);
  const selectedTopicReason = String(selectedTopicDiff.reason || "");
  const selectedTagReason = String(selectedTagDiff.reason || "");
  const isTopicUnavailable = String(selectedTopicDiff.status || "") !== "ok";
  const isTagUnavailable = String(selectedTagDiff.status || "") !== "ok";
  const reliabilityView = selectSourceReliabilityView(sourceReliability, mode, selectedTopicName, selectedTagName);
  const dataModeExtraParams = {
    mode,
    topic: mode === "within-topic" ? selectedTopicName : "",
    tag_slice: mode === "within-tag" ? selectedTagName : ""
  };

  return (
    <>
      <DataModeControls searchParams={searchParams} extraParams={dataModeExtraParams} />
      <div className="panel">
        <SectionHeader
          kicker="Scope"
          title="Analysis Mode"
          summary="Switch between pooled, within-topic, and within-tag source comparisons without changing the underlying data mode."
        />
        <div className="top-nav-links">
          <a
            className={`news-nav-link ${mode === "pooled" ? "active-link" : ""}`}
            href={analysisModeQueryHref("pooled", "", dataMode, snapshotDateValue)}
          >
            Pooled (topic-confounded)
          </a>
          <a
            className={`news-nav-link ${mode === "within-topic" ? "active-link" : ""}`}
            href={analysisModeQueryHref("within-topic", selectedTopicName, dataMode, snapshotDateValue)}
          >
            Within-topic
          </a>
          <a
            className={`news-nav-link ${mode === "within-tag" ? "active-link" : ""}`}
            href={analysisModeQueryHref("within-tag", "", dataMode, snapshotDateValue, { tag_slice: selectedTagName })}
          >
            Within-tag
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
        {mode === "within-tag" && tagSlices.length > 0 ? (
          <>
            <p className="muted" style={{ marginTop: "10px" }}>
              Tag slice
            </p>
            <div className="top-nav-links">
              {tagSlices.slice(0, 24).map((tag) => {
                const tagName = String(tag?.tag || "Unknown");
                const selected = tagName === selectedTagName;
                return (
                  <a
                    key={tagName}
                    className={`news-nav-link ${selected ? "active-link" : ""}`}
                    href={analysisModeQueryHref("within-tag", "", dataMode, snapshotDateValue, { tag_slice: tagName })}
                  >
                    {tagName}
                  </a>
                );
              })}
            </div>
          </>
        ) : null}
      </div>

      <SourceReliabilityBlock reliability={sourceReliability} />

      {mode === "pooled" ? (
        <SourceDifferentiationBlock
          title="Pooled Source Differentiation"
          differentiation={pooled}
          confounded
          reliability={reliabilityView}
        />
      ) : mode === "within-topic" && selectedTopic ? (
        <SourceDifferentiationBlock
          title={`Within-Topic Source Differentiation: ${selectedTopicName}`}
          differentiation={selectedTopicDiff}
          reliability={reliabilityView}
        />
      ) : mode === "within-tag" && selectedTagSlice ? (
        <SourceDifferentiationBlock
          title={`Within-Tag Source Differentiation: ${selectedTagName}`}
          differentiation={selectedTagDiff}
          reliability={reliabilityView}
        />
      ) : (
        <div className="panel">
          <SectionHeader
            kicker="Slice View"
            title={mode === "within-tag" ? "Within-Tag Source Differentiation" : "Within-Topic Source Differentiation"}
            summary="This slice is empty or currently unavailable under the selected constraints."
          />
          <EmptyState />
        </div>
      )}

      <div className="panel">
        <SectionHeader
          kicker="Reference Table"
          title="Topic Slice Overview"
          summary="Quick scan of per-topic separability, coverage, and held-out source classification strength."
        />
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
      <div className="panel">
        <SectionHeader
          kicker="Reference Table"
          title="Tag Slice Overview"
          summary="Quick scan of per-tag separability, coverage, and held-out source classification strength."
        />
        {mode === "within-tag" && selectedTagSlice && isTagUnavailable ? (
          <p className="muted">
            Selected tag is unavailable: {selectedTagReason || "Insufficient data for this tag slice."}
          </p>
        ) : null}
        {tagSlices.length === 0 ? (
          <EmptyState />
        ) : (
          <table className="news-table compact">
            <thead>
              <tr>
                <th>Tag</th>
                <th>Status</th>
                <th>Articles</th>
                <th>Sources</th>
                <th>F-stat</th>
                <th>LOOCV Acc</th>
              </tr>
            </thead>
            <tbody>
              {tagSlices.map((tag) => {
                const diff = asObject(tag.source_differentiation);
                const multi = asObject(diff.multivariate);
                const cls = asObject(diff.classification);
                return (
                  <tr key={String(tag.tag || "unknown-tag")}>
                    <td>{tag.tag || "Unknown"}</td>
                    <td>{String(diff.status || "unavailable")}</td>
                    <td>{formatNumber(tag.n_articles)}</td>
                    <td>{formatNumber(tag.n_sources)}</td>
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
