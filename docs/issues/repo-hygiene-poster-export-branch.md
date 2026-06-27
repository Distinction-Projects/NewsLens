# Issue: Move Poster Export Work Off Main Before Living Poster Integration

## Summary

`NewsLens/main` is synced with `origin/main`, but the local worktree contains uncommitted poster-export work directly on `main`. This should be moved to a dedicated `codex/` branch before building the living poster integration.

## Urgency

High. The living poster depends on NewsLens-generated stats and figures, so this work needs a clean branch/PR boundary before `NewsLensPoster` starts consuming it.

## Evidence

- `git status --short --branch` shows `main...origin/main` with modified and untracked files.
- Pending files include:
  - `.gitignore`
  - `README.md`
  - `requirements.txt`
  - `src/analytics/export_poster_figures.py`
  - `tests/test_poster_figure_export.py`
  - `docs/POSTER_FIGURE_DECISIONS.md`
  - `docs/issues/`
- The full NewsLens test suite passed locally: `461 tests OK`.

## Acceptance Criteria

- Move the poster-export work to a dedicated branch, for example `codex/poster-figure-export`.
- Commit the branch with the exporter, docs, dependency updates, and tests together.
- Open a PR or otherwise record review context for the feature.
- Keep `main` clean before starting the `NewsLensPoster` living-page branch.
- Re-run the full NewsLens test suite after the branch is created.

## Related Repos

- `NewsLensPoster`: daily living poster site and deployment.
- `RSS_Feeds`: upstream RSS quality and cleanliness diagnostics.
