const DEFAULT_BASE_URL = "http://127.0.0.1:9000";
const DEFAULT_REVALIDATE_SECONDS = 300;

export function newsApiBaseUrl() {
  const envValue = process.env.NEXT_PUBLIC_NEWS_API_BASE_URL;
  return (envValue || DEFAULT_BASE_URL).replace(/\/+$/, "");
}

export function newsFetchRevalidateSeconds() {
  const parsed = Number.parseInt(process.env.NEXT_PUBLIC_NEWS_FETCH_REVALIDATE_SECONDS || "", 10);
  if (Number.isFinite(parsed) && parsed >= 0) {
    return parsed;
  }
  return DEFAULT_REVALIDATE_SECONDS;
}

export async function fetchApiJson(path, options = {}) {
  const url = `${newsApiBaseUrl()}${path}`;
  const response = await fetch(url, {
    ...options,
    next: {
      revalidate: newsFetchRevalidateSeconds(),
      ...(options.next || {})
    }
  });
  if (!response.ok) {
    const body = await response.text();
    throw new Error(`Request failed (${response.status}) for ${url}: ${body}`);
  }
  return response.json();
}

export async function fetchNewsJson(path, options = {}) {
  return fetchApiJson(path, options);
}
