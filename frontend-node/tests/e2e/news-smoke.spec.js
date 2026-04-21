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
});
