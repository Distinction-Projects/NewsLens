import {
  asArray,
  asObject,
  buildQueryHref,
  fetchStatsForMode,
  formatDecimal,
  formatNumber,
  getQueryParam,
  getStatsDerived,
  normalizeDataMode,
  selectedSnapshotDateValue,
  toNumber
} from "../../../../lib/newsPageUtils";
import PlotlyChart from "../../../../components/PlotlyChart";
import {
  DataModeControls,
  EmptyState,
  SectionHeader,
  StatCard,
  StatusBlock,
  StatusPill
} from "../../../../components/news/NewsDashboardPrimitives";

const GROUP_TYPES = [
  { key: "source", label: "Sources" },
  { key: "topic", label: "Topics" },
  { key: "tag", label: "Tags" }
];

function normalizeGroupType(searchParams) {
  const raw = getQueryParam(searchParams, "group_type").toLowerCase();
  return GROUP_TYPES.some((option) => option.key === raw) ? raw : "source";
}

function groupHref(groupType, groupKey, dataMode, snapshot) {
  return buildQueryHref({
    group_type: groupType,
    group: groupKey,
    data_mode: dataMode,
    snapshot: dataMode === "snapshot" ? snapshot : ""
  });
}

function selectedGroupFromQuery(searchParams, rows) {
  const requested = getQueryParam(searchParams, "group");
  if (!requested) {
    return rows[0] || null;
  }
  return rows.find((row) => String(row?.group_key || "") === requested || String(row?.group || "") === requested) || rows[0] || null;
}

function numericRows(rows, xKey, yKey) {
  return rows
    .map((row) => ({
      ...row,
      x: toNumber(row?.[xKey]),
      y: toNumber(row?.[yKey]),
      count: toNumber(row?.n_articles) || 0,
      dispersion: toNumber(xKey.startsWith("pc") ? row?.dispersion_pca : row?.dispersion_mds)
    }))
    .filter((row) => row.x !== null && row.y !== null);
}

function topCountEntries(value, limit = 8) {
  return Object.entries(asObject(value))
    .map(([label, count]) => ({ label, count: toNumber(count) || 0 }))
    .sort((a, b) => b.count - a.count || a.label.localeCompare(b.label))
    .slice(0, limit);
}

function centroidChart(rows, selectedGroup, xKey, yKey, title) {
  const chartRows = numericRows(rows, xKey, yKey);
  const selectedKey = String(selectedGroup?.group_key || "");
  return {
    data: [
      {
        type: "scatter",
        mode: "markers",
        name: "Groups",
        x: chartRows.map((row) => row.x),
        y: chartRows.map((row) => row.y),
        text: chartRows.map((row) => String(row.group || "Unknown")),
        customdata: chartRows.map((row) => [row.n_articles, row.status, row.dispersion]),
        hovertemplate:
          "%{text}<br>Articles: %{customdata[0]}<br>Status: %{customdata[1]}<br>Dispersion: %{customdata[2]:.3f}<br>x: %{x:.3f}<br>y: %{y:.3f}<extra></extra>",
        marker: {
          size: chartRows.map((row) => Math.max(8, Math.min(28, Math.sqrt(row.count || 1) * 4))),
          color: chartRows.map((row) => (String(row.group_key || "") === selectedKey ? "#f0b36f" : "#7aa7ff")),
          opacity: chartRows.map((row) => (String(row.group_key || "") === selectedKey ? 1 : 0.72)),
          line: {
            color: chartRows.map((row) => (String(row.group_key || "") === selectedKey ? "#ffe3ba" : "#1f2f49")),
            width: chartRows.map((row) => (String(row.group_key || "") === selectedKey ? 2 : 1))
          }
        }
      }
    ],
    layout: {
      title,
      xaxis: { title: xKey.toUpperCase() },
      yaxis: { title: yKey.toUpperCase() }
    }
  };
}

function tagLensPcaChart(tagLensPca, selectedGroup) {
  const rows = asArray(tagLensPca?.tag_points)
    .map((row) => ({
      ...row,
      x: toNumber(row?.pc1),
      y: toNumber(row?.pc2),
      count: toNumber(row?.n_articles) || 0
    }))
    .filter((row) => row.x !== null && row.y !== null);
  const selectedKey = String(selectedGroup?.group_key || "");
  return {
    data: [
      {
        type: "scatter",
        mode: "markers+text",
        name: "Tags",
        x: rows.map((row) => row.x),
        y: rows.map((row) => row.y),
        text: rows.map((row) => String(row.tag || "Unknown")),
        textposition: "top center",
        customdata: rows.map((row) => [row.n_articles, row.n_sources]),
        hovertemplate:
          "%{text}<br>Articles: %{customdata[0]}<br>Sources: %{customdata[1]}<br>PC1: %{x:.3f}<br>PC2: %{y:.3f}<extra></extra>",
        marker: {
          size: rows.map((row) => Math.max(8, Math.min(28, Math.sqrt(row.count || 1) * 4))),
          color: rows.map((row) => (String(row.tag_key || "") === selectedKey ? "#f0b36f" : "#4fd1c5")),
          opacity: rows.map((row) => (String(row.tag_key || "") === selectedKey ? 1 : 0.75)),
          line: {
            color: rows.map((row) => (String(row.tag_key || "") === selectedKey ? "#ffe3ba" : "#183b43")),
            width: rows.map((row) => (String(row.tag_key || "") === selectedKey ? 2 : 1))
          }
        }
      }
    ],
    layout: {
      title: "Tag Mean Lens Profiles in PCA Space",
      xaxis: { title: "PC1" },
      yaxis: { title: "PC2" }
    }
  };
}

function GroupSelector({ rows, groupType, selectedGroup, dataMode, snapshot }) {
  return (
    <div className="top-nav-links group-selector-links">
      {rows.slice(0, 36).map((row) => {
        const groupKey = String(row?.group_key || row?.group || "");
        const selected = groupKey === String(selectedGroup?.group_key || "");
        return (
          <a
            key={groupKey}
            className={`news-nav-link ${selected ? "active-link" : ""}`}
            href={groupHref(groupType, groupKey, dataMode, snapshot)}
          >
            {row.group || "Unknown"} ({formatNumber(row.n_articles)})
          </a>
        );
      })}
    </div>
  );
}

function NearestGroupsTable({ selectedGroup }) {
  const rows = asArray(selectedGroup?.nearest_groups);
  if (rows.length === 0) {
    return <EmptyState>No nearest-neighbor rows available for this group.</EmptyState>;
  }
  return (
    <table className="news-table compact">
      <thead>
        <tr>
          <th>Neighbor</th>
          <th>PCA Distance</th>
        </tr>
      </thead>
      <tbody>
        {rows.map((row) => (
          <tr key={String(row.group_key || row.group)}>
            <td>{row.group || "Unknown"}</td>
            <td>{formatDecimal(row.distance_pca, 3)}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

function CountTable({ title, rows }) {
  if (rows.length === 0) {
    return null;
  }
  return (
    <div>
      <h4>{title}</h4>
      <table className="news-table compact">
        <tbody>
          {rows.map((row) => (
            <tr key={row.label}>
              <th>{row.label}</th>
              <td>{formatNumber(row.count)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export async function render(searchParams) {
  const payload = await fetchStatsForMode(searchParams);
  const derived = getStatsDerived(payload);
  const groupLatent = asObject(derived.group_latent_space);
  const tagLensPca = asObject(derived.tag_lens_pca);
  const tagLensPcaSummary = asObject(tagLensPca.summary);
  const groups = asObject(groupLatent.groups);
  const summary = asObject(groupLatent.summary);
  const config = asObject(groupLatent.config);
  const groupType = normalizeGroupType(searchParams);
  const rows = asArray(groups[groupType]);
  const dataMode = normalizeDataMode(searchParams);
  const snapshotDateValue = selectedSnapshotDateValue(searchParams);
  const selectedGroup = selectedGroupFromQuery(searchParams, rows);
  const pcaChart = centroidChart(rows, selectedGroup, "pc1", "pc2", `${GROUP_TYPES.find((item) => item.key === groupType)?.label || "Groups"} in PCA Space`);
  const mdsChart = centroidChart(rows, selectedGroup, "mds1", "mds2", `${GROUP_TYPES.find((item) => item.key === groupType)?.label || "Groups"} in MDS Space`);
  const tagProfileChart = tagLensPcaChart(tagLensPca, groupType === "tag" ? selectedGroup : null);
  const tagProfileRows = asArray(tagLensPca.tag_points);
  const lensDeviationRows = asArray(selectedGroup?.top_lens_deviations);
  const sourceRows = topCountEntries(selectedGroup?.source_counts);
  const topicRows = topCountEntries(selectedGroup?.topic_counts);
  const tagRows = topCountEntries(selectedGroup?.tag_counts);

  return (
    <>
      <DataModeControls
        searchParams={searchParams}
        extraParams={{
          group_type: groupType,
          group: selectedGroup?.group_key || selectedGroup?.group || ""
        }}
      />

      <div className="panel">
        <SectionHeader
          kicker="Latent Groups"
          title="Group Latent-Space Status"
          summary="Sources, topics, and tags are projected into the existing global lens PCA/MDS space so group positions stay comparable."
        />
        <StatusBlock status={String(groupLatent.status || "unavailable")} reason={String(groupLatent.reason || "")} />
        <div className="stats-grid">
          <StatCard label="Basis" value={groupLatent.basis || "n/a"} />
          <StatCard label="Tag Basis" value={config.tag_basis || "ai_tags"} />
          <StatCard label="Sources" value={formatNumber(asObject(summary.group_counts).source)} />
          <StatCard label="Topics" value={formatNumber(asObject(summary.group_counts).topic)} />
          <StatCard label="Tags" value={formatNumber(asObject(summary.group_counts).tag)} />
          <StatCard label="Analyzed Groups" value={formatNumber(summary.total_analyzed_groups)} />
          <StatCard label="Min Articles" value={formatNumber(config.min_articles_per_group)} />
        </div>
      </div>

      <div className="panel">
        <SectionHeader
          kicker="Controls"
          title="Group View"
          summary="Switch group type, then pick one group to highlight across the maps and detail tables."
        />
        <div className="top-nav-links">
          {GROUP_TYPES.map((option) => (
            <a
              key={option.key}
              className={`news-nav-link ${groupType === option.key ? "active-link" : ""}`}
              href={groupHref(option.key, "", dataMode, snapshotDateValue)}
            >
              {option.label}
            </a>
          ))}
        </div>
        {rows.length === 0 ? (
          <EmptyState>No groups available for this group type.</EmptyState>
        ) : (
          <GroupSelector rows={rows} groupType={groupType} selectedGroup={selectedGroup} dataMode={dataMode} snapshot={snapshotDateValue} />
        )}
      </div>

      <div className="panel">
        <SectionHeader
          kicker="Centroid Maps"
          title="Group Centroid Maps"
          summary="Bubble size follows article count. The selected group is highlighted; low-sample groups remain visible but should be interpreted cautiously."
        />
        {rows.length === 0 || (pcaChart.data[0].x.length === 0 && mdsChart.data[0].x.length === 0) ? (
          <EmptyState>No centroid coordinates available.</EmptyState>
        ) : (
          <div className="chart-grid">
            <PlotlyChart data={pcaChart.data} layout={pcaChart.layout} />
            <PlotlyChart data={mdsChart.data} layout={mdsChart.layout} />
          </div>
        )}
      </div>

      <div className="panel">
        <SectionHeader
          kicker="Tag Profiles"
          title="Tag Lens PCA"
          summary="A separate PCA where each tag is represented by its mean lens-score profile. Use this to see which tags have similar framing signatures."
        />
        <StatusBlock status={String(tagLensPca.status || "unavailable")} reason={String(tagLensPca.reason || "")} />
        <div className="stats-grid">
          <StatCard label="Basis" value={tagLensPca.basis || "n/a"} />
          <StatCard label="Tag Basis" value={asObject(tagLensPca.config).tag_basis || "ai_tags"} />
          <StatCard label="Included Tags" value={formatNumber(tagLensPcaSummary.included_tag_count)} />
          <StatCard label="Low-Sample Tags" value={formatNumber(tagLensPcaSummary.low_sample_tag_count)} />
          <StatCard label="Lenses" value={formatNumber(tagLensPca.n_lenses)} />
        </div>
        {tagProfileRows.length === 0 || tagProfileChart.data[0].x.length === 0 ? (
          <EmptyState>No tag lens-profile PCA coordinates available.</EmptyState>
        ) : (
          <>
            <div className="chart-grid">
              <PlotlyChart data={tagProfileChart.data} layout={tagProfileChart.layout} />
              <table className="news-table compact">
                <thead>
                  <tr>
                    <th>Tag</th>
                    <th>Articles</th>
                    <th>Sources</th>
                    <th>PC1</th>
                    <th>PC2</th>
                  </tr>
                </thead>
                <tbody>
                  {tagProfileRows.slice(0, 18).map((row) => (
                    <tr key={String(row.tag_key || row.tag)}>
                      <td>{row.tag || "Unknown"}</td>
                      <td>{formatNumber(row.n_articles)}</td>
                      <td>{formatNumber(row.n_sources)}</td>
                      <td>{formatDecimal(row.pc1, 3)}</td>
                      <td>{formatDecimal(row.pc2, 3)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </>
        )}
      </div>

      <div className="panel">
        <SectionHeader
          kicker="Selected Group"
          title={selectedGroup ? String(selectedGroup.group || "Selected Group") : "Selected Group"}
          summary="Centroid position, dispersion, sample size, and top lens deviations for the active group."
        />
        {!selectedGroup ? (
          <EmptyState>No selected group.</EmptyState>
        ) : (
          <>
            <p className="muted">
              <StatusPill tone={selectedGroup.status === "ok" ? "good" : "bad"}>{selectedGroup.status || "unknown"}</StatusPill>
              {selectedGroup.reason ? ` ${selectedGroup.reason}` : ""}
            </p>
            <div className="stats-grid">
              <StatCard label="Articles" value={formatNumber(selectedGroup.n_articles)} />
              <StatCard label="Sources" value={formatNumber(selectedGroup.n_sources)} />
              <StatCard label="Date Start" value={selectedGroup.date_start || "n/a"} />
              <StatCard label="Date End" value={selectedGroup.date_end || "n/a"} />
              <StatCard label="PCA Dispersion" value={formatDecimal(selectedGroup.dispersion_pca, 3)} />
              <StatCard label="MDS Dispersion" value={formatDecimal(selectedGroup.dispersion_mds, 3)} />
            </div>
            {lensDeviationRows.length > 0 ? (
              <div className="chart-grid">
                <PlotlyChart
                  data={[
                    {
                      type: "bar",
                      orientation: "h",
                      y: lensDeviationRows.map((row) => String(row.lens || "Unknown")).reverse(),
                      x: lensDeviationRows.map((row) => toNumber(row.delta) || 0).reverse(),
                      marker: {
                        color: lensDeviationRows
                          .map((row) => ((toNumber(row.delta) || 0) >= 0 ? "#4fd1c5" : "#f0b36f"))
                          .reverse()
                      },
                      customdata: lensDeviationRows
                        .map((row) => [toNumber(row.mean_percent), toNumber(row.corpus_mean_percent), toNumber(row.n)])
                        .reverse(),
                      hovertemplate:
                        "%{y}<br>Delta: %{x:.2f}<br>Group mean: %{customdata[0]:.2f}<br>Corpus mean: %{customdata[1]:.2f}<br>Rows: %{customdata[2]}<extra></extra>"
                    }
                  ]}
                  layout={{ title: "Top Lens Deviations from Corpus Mean", xaxis: { title: "Group minus corpus mean" } }}
                />
                <NearestGroupsTable selectedGroup={selectedGroup} />
              </div>
            ) : (
              <NearestGroupsTable selectedGroup={selectedGroup} />
            )}
          </>
        )}
      </div>

      {selectedGroup ? (
        <div className="panel">
          <SectionHeader
            kicker="Composition"
            title="Selected Group Composition"
            summary="The selected group's source, topic, and tag mix. These counts help separate coverage composition from latent-space position."
          />
          <div className="chart-grid">
            <CountTable title="Sources" rows={sourceRows} />
            <CountTable title="Topics" rows={topicRows} />
            <CountTable title="Tags" rows={tagRows} />
          </div>
        </div>
      ) : null}

      <div className="panel">
        <SectionHeader
          kicker="Reference Table"
          title="Group Centroids"
          summary="Ranked group centroid table for the active group type."
        />
        {rows.length === 0 ? (
          <EmptyState />
        ) : (
          <div className="table-scroll">
            <table className="news-table compact">
              <thead>
                <tr>
                  <th>Group</th>
                  <th>Status</th>
                  <th>Articles</th>
                  <th>Sources</th>
                  <th>PC1</th>
                  <th>PC2</th>
                  <th>MDS1</th>
                  <th>MDS2</th>
                  <th>PCA Dispersion</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((row) => (
                  <tr key={String(row.group_key || row.group)}>
                    <td>{row.group || "Unknown"}</td>
                    <td>{row.status || "unknown"}</td>
                    <td>{formatNumber(row.n_articles)}</td>
                    <td>{formatNumber(row.n_sources)}</td>
                    <td>{formatDecimal(row.pc1, 3)}</td>
                    <td>{formatDecimal(row.pc2, 3)}</td>
                    <td>{formatDecimal(row.mds1, 3)}</td>
                    <td>{formatDecimal(row.mds2, 3)}</td>
                    <td>{formatDecimal(row.dispersion_pca, 3)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </>
  );
}
