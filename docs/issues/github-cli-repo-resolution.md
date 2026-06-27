# Issue: Fix GitHub CLI Repo Resolution for NewsLens

## Summary

The local `NewsLens` checkout has both `origin` and `upstream` remotes. GitHub CLI commands resolve the default repository to `gabri-al/sarima_dashboard`, not `Distinction-Projects/NewsLens`, unless `-R Distinction-Projects/NewsLens` is passed explicitly.

## Urgency

High. This can cause issue, PR, and repo queries to target the wrong project while we are coordinating work across `NewsLens`, `RSS_Feeds`, and `NewsLensPoster`.

## Evidence

- `origin` points to `https://github.com/Distinction-Projects/NewsLens.git`.
- `upstream` points to `https://github.com/gabri-al/sarima_dashboard.git`.
- `branch.main.remote` is correctly set to `origin`.
- `gh repo view` from this checkout resolved to `gabri-al/sarima_dashboard`.
- `Distinction-Projects/NewsLens` has GitHub Issues disabled, so issue creation must be handled elsewhere unless the repo settings change.

## Acceptance Criteria

- Configure `gh` or repo metadata so default GitHub CLI operations target `Distinction-Projects/NewsLens`.
- Alternatively, document that every GitHub CLI command in this repo must use `-R Distinction-Projects/NewsLens`.
- Decide whether the legacy `upstream` remote is still needed.
- If GitHub Issues should be used for NewsLens work, enable Issues on `Distinction-Projects/NewsLens` or choose a canonical alternate tracker.
- Verify `gh repo view` and `gh pr list` return the intended NewsLens repository.

## Related Repos

- `NewsLensPoster`: living poster work will depend on NewsLens stats/export artifacts.
- `RSS_Feeds`: upstream pipeline issues are tracked in its own enabled issue tracker.
