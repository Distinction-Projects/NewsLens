import Link from "next/link";
import { newsApiBaseUrl } from "../../lib/newsApi";
import { fetchNewsFreshness, newsFreshnessView } from "../../lib/newsFreshness.mjs";

export default async function NewsFreshness() {
  let payload = null;
  try {
    payload = await fetchNewsFreshness(newsApiBaseUrl());
  } catch {
    // A status check must not prevent access to saved articles and charts.
  }
  const view = newsFreshnessView(payload);
  return (
    <aside className={`news-freshness news-freshness-${view.state}`} aria-label="Feed status">
      <span className="news-freshness-dot" aria-hidden="true" />
      <div>
        {view.dateTime ? <time dateTime={view.dateTime}>{view.label}</time> : <span>{view.label}</span>}
        {view.state === "stale" ? <span className="muted"> Updates are delayed. You are viewing the saved collection.</span> : null}
      </div>
      <Link href="/news/workflow-status">Update status</Link>
    </aside>
  );
}
