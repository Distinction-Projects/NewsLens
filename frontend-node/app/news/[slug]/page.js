import { notFound } from "next/navigation";
import { getNewsPage } from "../../../lib/newsPages";
import { PageIntro } from "../../../components/news/NewsDashboardPrimitives";
import { renderNewsPageBody } from "./renderers";

export const dynamic = "force-dynamic";

export default async function NewsDetailPage({ params, searchParams }) {
  const page = getNewsPage(params.slug);
  if (!page) {
    notFound();
  }

  let body = null;
  let errorMessage = null;
  try {
    body = await renderNewsPageBody(page.slug, searchParams);
  } catch (error) {
    errorMessage = error instanceof Error ? error.message : String(error);
  }

  return (
    <>
      <div className="page-title-row">
        <h1>{page.title}</h1>
      </div>
      <PageIntro summary={page.summary} />

      {errorMessage ? (
        <div className="panel">
          <h3>API Error</h3>
          <p className="muted">This view could not load its data. Please try again shortly, or browse another view.</p>
          <a className="news-nav-link" href="">Try again</a>
          <details className="news-error-details">
            <summary>Technical details</summary>
            <p className="muted">{errorMessage}</p>
          </details>
        </div>
      ) : (
        body
      )}
    </>
  );
}
