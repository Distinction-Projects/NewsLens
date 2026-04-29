import "./globals.css";
import Link from "next/link";
import { publicSiteUrl } from "../lib/siteConfig";

export const metadata = {
  metadataBase: new URL(publicSiteUrl()),
  title: "NewsLens Research Dashboard",
  description: "Public research dashboard for sentiment models and AI news analytics",
  alternates: {
    canonical: "/"
  },
  openGraph: {
    title: "NewsLens Research Dashboard",
    description: "Public research dashboard for sentiment models and AI news analytics",
    url: "/",
    siteName: "NewsLens",
    type: "website"
  }
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
