import { fetchNewsJson } from "./newsApi";

export function asArray(value) {
  return Array.isArray(value) ? value : [];
}

export function asObject(value) {
  return value && typeof value === "object" && !Array.isArray(value) ? value : {};
}

export function toNumber(value) {
  const number = typeof value === "number" ? value : Number(value);
  return Number.isFinite(number) ? number : null;
}

export function formatNumber(value) {
  const number = toNumber(value);
  if (number === null) {
    return "n/a";
  }
  return new Intl.NumberFormat("en-US").format(number);
}

export function formatDecimal(value, digits = 2) {
  const number = toNumber(value);
  if (number === null) {
    return "n/a";
  }
  return number.toFixed(digits);
}

export function formatPercent(value) {
  const number = toNumber(value);
  if (number === null) {
    return "n/a";
  }
  return `${(number * 100).toFixed(1)}%`;
}

export function formatAlreadyPercent(value) {
  const number = toNumber(value);
  if (number === null) {
    return "n/a";
  }
  return `${number.toFixed(1)}%`;
}

export function truncateText(value, maxLength = 220) {
  const text = typeof value === "string" ? value : JSON.stringify(value);
  if (!text) {
    return "n/a";
  }
  return text.length > maxLength ? `${text.slice(0, maxLength)}...` : text;
}

export async function fetchStatsPayload(snapshotDate = null) {
  const query = typeof snapshotDate === "string" && snapshotDate ? `?snapshot_date=${encodeURIComponent(snapshotDate)}` : "";
  return fetchNewsJson(`/api/news/stats${query}`);
}

export function getStatsDerived(payload) {
  return asObject(asObject(payload?.data).derived);
}

export function snapshotDateFromSearchParams(searchParams) {
  const raw = typeof searchParams?.snapshot === "string" ? searchParams.snapshot.trim() : "";
  return /^\d{4}-\d{2}-\d{2}$/.test(raw) ? raw : null;
}

export function getQueryParam(searchParams, key) {
  const raw = searchParams?.[key];
  if (typeof raw === "string") {
    return raw.trim();
  }
  if (Array.isArray(raw) && typeof raw[0] === "string") {
    return raw[0].trim();
  }
  return "";
}

export function normalizeMode(searchParams) {
  const raw = getQueryParam(searchParams, "mode").toLowerCase();
  return raw === "within-topic" ? "within-topic" : "pooled";
}

export function normalizeDataMode(searchParams) {
  const raw = getQueryParam(searchParams, "data_mode").toLowerCase();
  return raw === "snapshot" ? "snapshot" : "current";
}

export function selectedSnapshotDateValue(searchParams) {
  const raw = getQueryParam(searchParams, "snapshot");
  return raw || "";
}

export function activeSnapshotDate(searchParams) {
  const date = snapshotDateFromSearchParams(searchParams);
  const mode = normalizeDataMode(searchParams);
  if (mode === "snapshot" && date) {
    return date;
  }
  return null;
}

export function isTruthyQueryValue(raw) {
  const value = String(raw || "").trim().toLowerCase();
  return value === "1" || value === "true" || value === "yes" || value === "on";
}

export function queryLimit(searchParams, key, fallback, min = 1, max = 500) {
  const raw = getQueryParam(searchParams, key);
  const parsed = Number(raw);
  if (!Number.isFinite(parsed)) {
    return fallback;
  }
  return Math.max(min, Math.min(max, Math.trunc(parsed)));
}

export function sourceCountsToRows(sourceCountsValue) {
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

export function selectedTopicFromQuery(searchParams, topics) {
  const requested = getQueryParam(searchParams, "topic");
  if (!requested) {
    return topics[0] || null;
  }
  return topics.find((topic) => String(topic?.topic || "") === requested) || topics[0] || null;
}

export function selectSourceReliabilityView(sourceReliability, mode, selectedTopic) {
  const reliability = asObject(sourceReliability);
  const pooled = asObject(reliability.pooled);
  if (mode !== "within-topic" || !selectedTopic) {
    return pooled;
  }
  const topicRows = asArray(reliability.topics);
  const match = topicRows.find((row) => String(row?.topic || "") === selectedTopic);
  return asObject(match?.assessment) || pooled;
}

export function buildQueryHref(paramsObject) {
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

export function analysisModeQueryHref(mode, topic, dataMode, snapshot, extraParams = {}) {
  return buildQueryHref({
    ...extraParams,
    mode,
    topic,
    data_mode: dataMode,
    snapshot: dataMode === "snapshot" ? snapshot : ""
  });
}

export function dataModeQueryHref(dataMode, snapshot, extraParams = {}) {
  return buildQueryHref({
    ...extraParams,
    data_mode: dataMode,
    snapshot: dataMode === "snapshot" ? snapshot : ""
  });
}

export async function fetchStatsForMode(searchParams) {
  const snapshotDate = activeSnapshotDate(searchParams);
  return fetchStatsPayload(snapshotDate);
}
