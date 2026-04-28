import { newsApiBaseUrl } from "../../../../lib/newsApi";
import {
  asArray,
  asObject,
  getQueryParam,
  getStatsDerived,
  queryLimit,
  sourceCountsToRows,
  toNumber,
  truncateText
} from "../../../../lib/newsPageUtils";
import { StatusPill } from "../../../../components/news/NewsDashboardPrimitives";

export { sourceCountsToRows };

export function getCorrelationPairRows(lenses, matrix) {
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

export function normalizedSourceEffectsFilter(searchParams) {
  const allowedMaxLens = new Set([5, 10, 15, 20]);
  const allowedQThreshold = new Set([1.0, 0.1, 0.05, 0.01]);
  const maxLensesRaw = queryLimit(searchParams, "max_lenses", 10, 1, 20);
  const qThresholdRaw = toNumber(getQueryParam(searchParams, "q_threshold"));
  return {
    maxLenses: allowedMaxLens.has(maxLensesRaw) ? maxLensesRaw : 10,
    qThreshold: qThresholdRaw !== null && allowedQThreshold.has(qThresholdRaw) ? qThresholdRaw : 1.0
  };
}

export async function fetchEndpointStatus(label, path, options = {}) {
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

export function EndpointTable({ rows }) {
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

export function extractSnapshotMetrics(payload) {
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

export function metricDelta(current, snapshot) {
  if (current === null || snapshot === null) {
    return "n/a";
  }
  const delta = current - snapshot;
  return Number.isInteger(delta) ? `${delta >= 0 ? "+" : ""}${delta}` : `${delta >= 0 ? "+" : ""}${delta.toFixed(1)}`;
}

export function pairKey(a, b) {
  return `${String(a || "")}\u0000${String(b || "")}`;
}
