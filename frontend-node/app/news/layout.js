import NewsNavigation from "../../components/news/NewsNavigation";
import NewsFreshness from "../../components/news/NewsFreshness";

export default function NewsLayout({ children }) {
  return (
    <main className="news-layout-page">
      <NewsNavigation />
      <NewsFreshness />
      <div id="news-content">{children}</div>
    </main>
  );
}
