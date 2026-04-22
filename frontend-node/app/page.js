import Link from "next/link";

export default function HomePage() {
  return (
    <main>
      <h1>NewsLens Node Frontend</h1>
      <p className="muted">
        This frontend consumes FastAPI endpoints while Dash routes are migrated over in stages.
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
            <Link href="/news">/news</Link> migrated news analytics pages
          </li>
        </ul>
      </div>

      <div className="panel">
        <h2>Migration State</h2>
        <p>
          Dash remains online for parity, but the new default path is FastAPI + Next.js.
        </p>
      </div>
    </main>
  );
}
