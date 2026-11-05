export async function fetchNewsFreshness(baseUrl, { fetchImpl = fetch, timeoutMs = 3000 } = {}) {
  const response = await fetchImpl(`${baseUrl}/health/news-freshness`, {
    signal: AbortSignal.timeout(timeoutMs),
    next: { revalidate: 300 }
  });
  const payload = await response.json();
  // The health endpoint deliberately returns 503 when the saved feed is stale.
  if (!response.ok && !(response.status === 503 && payload?.status === "stale")) {
    throw new Error(`Feed status unavailable (${response.status})`);
  }
  return payload;
}

export function newsFreshnessView(payload, now = Date.now()) {
  const timestamp = payload?.generated_at;
  const date = typeof timestamp === "string" ? new Date(timestamp) : null;
  if (!date || !Number.isFinite(date.getTime())) {
    return { state: "unknown", dateTime: null, label: "Feed update date unavailable" };
  }

  const maxAge = Number(payload.max_age_seconds);
  const maxAgeMs = Number.isFinite(maxAge) && maxAge > 0 ? maxAge * 1000 : 48 * 60 * 60 * 1000;
  const stale = payload.is_fresh === false || payload.status === "stale" || now - date.getTime() > maxAgeMs;
  return {
    state: stale ? "stale" : "fresh",
    dateTime: date.toISOString(),
    label: `Latest feed update: ${date.toLocaleDateString("en-US", {
      month: "short", day: "numeric", year: "numeric", timeZone: "UTC"
    })}`
  };
}
