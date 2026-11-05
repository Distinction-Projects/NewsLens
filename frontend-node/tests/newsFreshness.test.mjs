import assert from "node:assert/strict";
import test from "node:test";
import { fetchNewsFreshness, newsFreshnessView } from "../lib/newsFreshness.mjs";

const now = Date.parse("2026-11-05T12:00:00Z");

test("a stale 503 health response retains its timestamp", async () => {
  const payload = { status: "stale", is_fresh: false, generated_at: "2026-07-20T15:30:36Z" };
  const fetchImpl = async (url, options) => {
    assert.equal(url, "http://example.test/health/news-freshness");
    assert.ok(options.signal instanceof AbortSignal);
    assert.equal(options.next.revalidate, 300);
    return Response.json(payload, { status: 503 });
  };
  assert.deepEqual(await fetchNewsFreshness("http://example.test", { fetchImpl }), payload);
});

test("successful health data is returned unchanged", async () => {
  const payload = { status: "ok", generated_at: "2026-11-05T10:00:00Z" };
  assert.deepEqual(await fetchNewsFreshness("http://example.test", {
    fetchImpl: async () => Response.json(payload)
  }), payload);
});

test("unrelated health failures are not presented as a stale collection", async () => {
  await assert.rejects(fetchNewsFreshness("http://example.test", {
    fetchImpl: async () => Response.json({ status: "upstream_error" }, { status: 503 })
  }), /Feed status unavailable/);
});

test("invalid health JSON is rejected", async () => {
  await assert.rejects(fetchNewsFreshness("http://example.test", {
    fetchImpl: async () => new Response("not json", { status: 503 })
  }), SyntaxError);
});

test("old data is dated and marked stale even if the API calls it fresh", () => {
  const view = newsFreshnessView({ generated_at: "2026-07-20T15:30:36Z", is_fresh: true }, now);
  assert.equal(view.state, "stale");
  assert.equal(view.label, "Latest feed update: Jul 20, 2026");
});

test("recent data uses the backend freshness threshold", () => {
  const payload = { generated_at: "2026-11-05T10:00:00Z", max_age_seconds: 3600 };
  assert.equal(newsFreshnessView(payload, now).state, "stale");
  assert.equal(newsFreshnessView({ ...payload, max_age_seconds: 172800 }, now).state, "fresh");
});

test("explicit stale status is respected for a recent timestamp", () => {
  const payload = { generated_at: "2026-11-05T11:59:00Z" };
  assert.equal(newsFreshnessView({ ...payload, is_fresh: false }, now).state, "stale");
  assert.equal(newsFreshnessView({ ...payload, status: "stale" }, now).state, "stale");
});

test("missing or invalid health data remains unknown", () => {
  for (const payload of [null, {}, { generated_at: null }, { generated_at: "invalid" }]) {
    const view = newsFreshnessView(payload, now);
    assert.equal(view.state, "unknown");
    assert.equal(view.dateTime, null);
    assert.equal(view.label, "Feed update date unavailable");
  }
});
