const { test, expect } = require("@playwright/test");

const NEWS_ROUTE_EXPECTATIONS = [
  { path: "/news/digest", heading: "News Digest" },
  { path: "/news/stats", heading: "News Stats" },
  { path: "/news/sources", heading: "News Sources" },
  { path: "/news/lenses", heading: "News Lenses" },
  { path: "/news/lens-matrix", heading: "News Lens Matrix" },
  { path: "/news/lens-correlations", heading: "News Lens Correlations" },
  { path: "/news/lens-pca", heading: "News Lens PCA" },
  { path: "/news/source-differentiation", heading: "News Source Differentiation" },
  { path: "/news/source-effects", heading: "News Source Effects" },
  { path: "/news/score-lab", heading: "News Score Lab" },
  { path: "/news/lens-explorer", heading: "News Lens Explorer" },
  { path: "/news/lens-by-source", heading: "News Lens by Source" },
  { path: "/news/lens-stability", heading: "News Lens Stability" },
  { path: "/news/tags", heading: "News Tags" },
  { path: "/news/source-tag-matrix", heading: "News Source Tag Matrix" },
  { path: "/news/trends", heading: "News Trends" },
  { path: "/news/scraped", heading: "News Scraped" },
  { path: "/news/workflow-status", heading: "News Workflow Status" },
  { path: "/news/data-quality", heading: "News Data Quality" },
  { path: "/news/snapshot-compare", heading: "News Snapshot Compare" },
  { path: "/news/raw-json", heading: "News Raw JSON" },
  { path: "/news/integration", heading: "News Integration" }
];

test("news shell routes render", async ({ page, baseURL }) => {
  await page.goto(`${baseURL}/news`);
  await expect(page.getByRole("heading", { name: "News", exact: true })).toBeVisible();
  const digestNavLink = page.locator('nav.news-nav-grid a[href="/news/digest"]').first();
  await expect(digestNavLink).toBeVisible();

  await digestNavLink.click();
  await expect(page).toHaveURL(/\/news\/digest$/);
  await expect(page.getByRole("heading", { name: "News Digest" })).toBeVisible();

  for (const { path, heading } of NEWS_ROUTE_EXPECTATIONS) {
    await page.goto(`${baseURL}${path}`);
    await expect(page.getByRole("heading", { name: heading })).toBeVisible();
    await expect(page.getByText("Live FastAPI data")).toBeVisible();
    await expect(page.locator("details.news-page-intro summary")).toContainText("What this page does");
    await expect(page.getByRole("heading", { name: "Migration In Progress" })).toHaveCount(0);
  }
});

test("news scraped route shows raw payload explorer controls", async ({ page, baseURL }) => {
  await page.goto(`${baseURL}/news/scraped`);
  await expect(page.getByRole("heading", { name: "News Scraped" })).toBeVisible();
  const filtersHeading = page.getByRole("heading", { name: "Scraped Filters" });
  if ((await filtersHeading.count()) > 0) {
    await expect(filtersHeading).toBeVisible();
    await expect(page.locator('input[name="source"]')).toBeVisible();
    await expect(page.locator('input[name="limit"]')).toBeVisible();
    await expect(page.locator('select[name="only"]')).toBeVisible();
    await expect(page.getByRole("button", { name: "Apply" })).toBeVisible();
    await expect(page.getByRole("link", { name: "Refresh" })).toBeVisible();
    await expect(page.getByRole("heading", { name: "Raw Scraped Article Data" })).toBeVisible();
    await expect(page.getByRole("heading", { name: "Grouped by Source" })).toBeVisible();
  } else {
    await expect(page.getByRole("heading", { name: "API Error" })).toBeVisible();
  }
});

test("source differentiation supports pooled and within-topic modes", async ({ page, baseURL }) => {
  await page.goto(`${baseURL}/news/source-differentiation`);
  await expect(page.getByRole("heading", { name: "News Source Differentiation" })).toBeVisible();

  const apiErrorHeading = page.getByRole("heading", { name: "API Error" });
  if ((await apiErrorHeading.count()) > 0) {
    await expect(apiErrorHeading).toBeVisible();
    return;
  }

  await expect(page.getByRole("link", { name: "Pooled (topic-confounded)" })).toBeVisible();
  await expect(page.getByRole("link", { name: "Within-topic" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Pooled Source Differentiation" })).toBeVisible();
  await expect(page.getByText("Label: topic-confounded")).toBeVisible();

  await page.getByRole("link", { name: "Within-topic" }).click();
  await expect(page).toHaveURL(/\/news\/source-differentiation\?mode=within-topic/);
  await expect(page.getByRole("heading", { name: /Within-Topic Source Differentiation/ })).toBeVisible();
  const topicLinks = page.locator('a[href*="mode=within-topic"][href*="topic="]');
  if ((await topicLinks.count()) > 0) {
    await expect(topicLinks.first()).toBeVisible();
  } else {
    await expect(page.getByText("No topic slices available for this dataset.")).toBeVisible();
  }
});

test("source effects supports pooled and within-topic modes", async ({ page, baseURL }) => {
  await page.goto(`${baseURL}/news/source-effects`);
  await expect(page.getByRole("heading", { name: "News Source Effects" })).toBeVisible();

  const apiErrorHeading = page.getByRole("heading", { name: "API Error" });
  if ((await apiErrorHeading.count()) > 0) {
    await expect(apiErrorHeading).toBeVisible();
    return;
  }

  await expect(page.getByRole("link", { name: "Pooled (topic-confounded)" })).toBeVisible();
  await expect(page.getByRole("link", { name: "Within-topic" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Pooled Source Effects" })).toBeVisible();
  await expect(page.getByText("Label: topic-confounded")).toBeVisible();

  await page.getByRole("link", { name: "Within-topic" }).click();
  await expect(page).toHaveURL(/mode=within-topic/);
  await expect(page.getByRole("heading", { name: /Within-Topic Source Effects/ })).toBeVisible();
  const topicLinks = page.locator('a[href*="mode=within-topic"][href*="topic="]');
  if ((await topicLinks.count()) > 0) {
    await expect(topicLinks.first()).toBeVisible();
  } else {
    await expect(page.getByText("No topic slices available for this dataset.")).toBeVisible();
  }
});
