# Site Review and Focused Review Handoff

Checked November 5, 2026. The findings below describe the state before recovery; see the release record for the latest verified work.

## Workspace

- App: `/Users/alexstevens/Documents/GitHub/NewsLens`.
- Upstream: `/Users/alexstevens/Documents/GitHub/RSS_Feeds`.
- `NEWSLENS_RSS` refers to these two repositories, not a third repository.
- Public site: https://lab.spectralresidue.com/.

## Verified Findings Before Recovery

- The public homepage and stats endpoint respond successfully.
- `/health/news-freshness` reports stale data generated July 20, 2026, not a current news collection.
- GitHub history confirms the upstream artifact itself was last updated July 20, not just an old app cache: https://github.com/Distinction-Projects/RSS_Feeds/commit/e81c6d1c5ab22294a9c16802880df38d34b8c473.
- Live stats contain 4,611 articles but only 172 lens-scored articles. Do not present these denominators as interchangeable.
- Live stats report `stats_backend=dynamic` and `stats_backend_fallback=precomputed_unavailable`. A working endpoint does not prove the production snapshot job is healthy.
- Both the RSS daily workflow and NewsLens droplet deployment workflow have GitHub state `disabled_inactivity`.
- The latest recorded RSS digest run, September 18, passed digest generation and its quality check, then failed the broader feed audit: `feed_fetch_failed: 2 > 0`. Scoring, precomputed JSON building, and publication were skipped.
- Evidence: https://github.com/Distinction-Projects/RSS_Feeds/actions/runs/35371953608.
- This explains that run's publication failure. It does not by itself explain every failure since July.

## Local Usability Changes

- Replaced the repeated hero and 25-page directory above every news view with compact navigation and a collapsed, grouped directory.
- Simplified the homepage and news index around articles, tags, comparisons, and temporal views.
- Kept all 25 routes, charts, and analytical calculations unchanged.
- Added a visible feed date and stale-data notice, including the health endpoint's intentional HTTP 503 stale response.
- Added keyboard focus/skip navigation and a scrollable article table rather than making the whole mobile page scroll sideways.
- Added aligned filter labels/controls and stacked mobile fields without changing query parameters.
- Added freshness unit tests, mobile/navigation tests, and completed Plotly SVG checks.
- The existing RSS_Feeds checkout's untracked source-health artifact was left untouched. Publication fixes were developed in an isolated checkout.

## Release Record

- RSS publication policy is implemented and merged: https://github.com/Distinction-Projects/RSS_Feeds/pull/24 (main commit `9408b6e7bb0c0fc8641fad0e7ae840b782179ba7`).
- Limited feed transport failures are warnings only when at least 80% of audited feeds succeed and eligible articles exist. Content gates still block publication. Full outages and empty collections fail.
- The RSS workflow is enabled again. A recovery run is in progress with 24 sources, one item per feed, at most four scored articles, cache reuse, and no forced rescore: https://github.com/Distinction-Projects/RSS_Feeds/actions/runs/42125796583.
- The app release preserves runtime caches/snapshots, moves scheduled deployment after RSS publication, and rejects stale/dynamic-fallback stats in its smoke checks. Live deployment verification is still pending.
- App backend: 467 tests pass. RSS: 103 offline tests and serialization/quality/publication checks pass; CI lint, format, typing and smoke checks pass. Next build, freshness tests, renderer guard and fixture browser checks pass.

## Next Work, In Order

1. Verify the bounded RSS recovery run publishes a new upstream artifact.
2. Deploy the tested UI and regenerate the production stats snapshot; require precomputed backend metadata without fallback.
3. Recheck live freshness, article/lens coverage, representative tag/source charts, and mobile navigation after deployment.

## When Astra Is Useful

Routine UI changes, test failures, log inspection, and the established publication failure do not currently require an escalation. A focused independent review may help with the cross-repository publication policy or statistical interpretation of sparsely scored slices. Using a larger model does not replace evidence or a project-owner policy decision.

Use this one-pass prompt if those questions remain unresolved:

```text
Review NewsLens and its sibling RSS_Feeds read-only. Start with
docs/SITE_REVIEW_AND_ASTRA_HANDOFF.md and inspect the actual code before
drawing conclusions. Do not treat the full chat history as verified state.

Answer only:
1. How can valid articles publish when unrelated feeds fail, without
   admitting incomplete or ineligible article content?
2. Where should freshness, scored-sample coverage, and degraded source
   coverage be represented so the app cannot imply more than the data supports?
3. What is the smallest safe sequence to restore upstream publication,
   precomputed analytics, and the public site?

Give at most five prioritized findings with file/line evidence, distinguish
verified facts from hypotheses, and recommend one next implementation step
with tests. Stop after the review. Do not edit, deploy, enable workflows,
run paid model calls, or initiate a bulk rescore. If evidence is sufficient,
say that no further high-reasoning review is necessary.
```

Return to the regular implementation model after that decision/review. Do not use an open-ended "perfect the entire codebase" prompt or parallel reviews that repeat the same evidence gathering.

## Local Checks

```sh
npm --prefix frontend-node run test:news-freshness
npm --prefix frontend-node run check:news-renderers
npm --prefix frontend-node run build
npm --prefix frontend-node run e2e:smoke
npm --prefix frontend-node run e2e:smoke:live
git diff --check
```

Browser fixture runs disable event embedding calls. Local browser success is not production verification.

Results this run: production build passes; 8 freshness unit tests pass; 25 renderer modules pass the structural guard; the full 14-test browser suite passes. The production-build rerun passes all 13 targeted fixture tests plus the separate 25-route sweep. Desktop and mobile screenshots were inspected. Release validation also passes all 467 backend tests and repeats the 13-test fixture browser checks with event embeddings disabled.
