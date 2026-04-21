import Link from "next/link";

export default function HomePage() {
  return (
    <main>
      <h1>NewsLens Node Frontend (Starter)</h1>
      <p className="muted">
        This is the initial split-architecture frontend. It consumes the FastAPI backend, while the Dash app remains unchanged.
      </p>
      <div className="panel">
        <h2>Next Step</h2>
        <p>
          Open <Link href="/news">/news</Link> to verify live reads from FastAPI news endpoints.
        </p>
      </div>
    </main>
  );
}
