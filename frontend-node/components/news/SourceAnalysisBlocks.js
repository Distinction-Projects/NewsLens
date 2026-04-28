import PlotlyChart from "../PlotlyChart";
import {
  asArray,
  asObject,
  formatDecimal,
  formatNumber,
  formatPercent,
  sourceCountsToRows,
  toNumber
} from "../../lib/newsPageUtils";
import { EmptyState, StatCard, StatusBlock } from "./NewsDashboardPrimitives";

export function SourceDifferentiationBlock({ title, differentiation, confounded = false, reliability }) {
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

export function SourceEffectsBlock({ title, effects, confounded = false, maxLenses, qThreshold, selectedLens, reliability }) {
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
