const DEFAULT_BASE_URL = "http://127.0.0.1:9000";

export function newsApiBaseUrl() {
  const envValue = process.env.NEXT_PUBLIC_NEWS_API_BASE_URL;
  return (envValue || DEFAULT_BASE_URL).replace(/\/+$/, "");
}

export async function fetchNewsJson(path) {
  const url = `${newsApiBaseUrl()}${path}`;
  const response = await fetch(url, {
    next: { revalidate: 60 }
  });
  if (!response.ok) {
    const body = await response.text();
    throw new Error(`Request failed (${response.status}) for ${url}: ${body}`);
  }
  return response.json();
}
