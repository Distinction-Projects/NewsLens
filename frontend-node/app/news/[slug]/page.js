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
        <h2>{page.title}</h2>
        <p className="muted">Live FastAPI data</p>
      </div>
      <PageIntro summary={page.summary} />

      {errorMessage ? (
        <div className="panel">
          <h3>API Error</h3>
          <p className="muted">{errorMessage}</p>
          <p>
            Ensure FastAPI is running: <code>uvicorn src.api.fastapi_app:app --reload --port 9000</code>
          </p>
        </div>
      ) : (
        body
      )}
    </>
  );
}
