import Link from "next/link";

export default function HomePage() {
  return (
    <main>
      <h1>NewsLens Node Frontend</h1>
      <p className="muted">
        This frontend consumes FastAPI endpoints and now includes full `/news/*` route coverage.
      </p>

      <div className="panel">
        <h2>Available Pages</h2>
        <ul>
          <li>
            <Link href="/evaluation">/evaluation</Link> model metrics by corpus
          </li>
          <li>
            <Link href="/text">/text</Link> interactive sentiment analysis
          </li>
          <li>
            <Link href="/about">/about</Link> project method and stack direction
          </li>
          <li>
            <Link href="/news">/news</Link> full news analytics surface
          </li>
          <li>
            <Link href="/supabase-test">/supabase-test</Link> Supabase connectivity check
          </li>
        </ul>
      </div>

      <div className="panel">
        <h2>Architecture State</h2>
        <p>
          Dash remains online for parity and historical validation, while FastAPI + Next.js is the primary frontend path.
        </p>
      </div>
    </main>
  );
}
