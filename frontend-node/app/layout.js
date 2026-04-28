import "./globals.css";
import Link from "next/link";

export const metadata = {
  title: "NewsLens Research Dashboard",
  description: "Public research dashboard for sentiment models and AI news analytics"
};

export default function RootLayout({ children }) {
  return (
    <html lang="en">
      <body>
        <header className="top-nav-wrap">
          <nav className="top-nav">
            <Link href="/" className="top-nav-brand">
              NewsLens
            </Link>
            <div className="top-nav-links">
              <Link href="/evaluation">Evaluation</Link>
              <Link href="/text">Text</Link>
              <Link href="/about">About</Link>
              <Link href="/news">News</Link>
            </div>
          </nav>
        </header>
        {children}
      </body>
    </html>
  );
}
