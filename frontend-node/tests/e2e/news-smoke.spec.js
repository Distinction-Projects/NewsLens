const { test, expect } = require("@playwright/test");

test("news shell routes render", async ({ page, baseURL }) => {
  await page.goto(`${baseURL}/news`);
  await expect(page.getByRole("heading", { name: "News" })).toBeVisible();
  const digestNavLink = page.locator('nav.news-nav-grid a[href="/news/digest"]').first();
  await expect(digestNavLink).toBeVisible();

  await digestNavLink.click();
  await expect(page).toHaveURL(/\/news\/digest$/);
  await expect(page.getByRole("heading", { name: "News Digest" })).toBeVisible();

  await page.goto(`${baseURL}/news/stats`);
  await expect(page.getByRole("heading", { name: "News Stats" })).toBeVisible();

  await page.goto(`${baseURL}/news/sources`);
  await expect(page.getByRole("heading", { name: "News Sources" })).toBeVisible();

  for (const path of ["/news/lenses", "/news/tags", "/news/source-tag-matrix", "/news/trends", "/news/data-quality"]) {
    await page.goto(`${baseURL}${path}`);
    await expect(page.getByText("Live FastAPI data")).toBeVisible();
    await expect(page.getByRole("heading", { name: "Migration In Progress" })).toHaveCount(0);
  }
});
