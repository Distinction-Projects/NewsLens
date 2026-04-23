# Codex Task Safety Playbook

This repo uses long-running cloud agent tasks and local command execution. Cancellation is not always reliable, so prevention is the primary control.

## Stuck-run playbook

1. Try one normal cancel/stop action in the UI/integration.
2. If cancel fails, abandon the thread/session and start a new one.
3. Re-run with tighter scope and non-interactive command flags.
4. If local tooling is wedged, restart the terminal/IDE panel/window.

## Why this happens

- Agent runs are long-lived jobs in remote/containerized environments.
- Blocking prompts, loops, or deadlocked setup/tests may ignore cancellation.
- Some clients still have partial cancellation behavior.

## Operational guardrails

- Do not run interactive commands that can prompt for input.
- Always choose non-interactive flags where available.
- Prefer bounded workloads:
  - subset tests/data first
  - explicit limits/time windows/sample sizes
  - no watcher loops unless explicitly requested
- Break large work into scoped steps with checkpoints.

## Safe task template (use this by default)

Use this format when starting a task:

1. Objective: one concrete deliverable.
2. Scope: files/modules/routes to touch.
3. Constraints:
   - non-interactive commands only
   - bounded datasets/tests
   - no long-running watchers
4. Validation:
   - exact commands to run
   - expected pass/fail signal
5. Rollback:
   - what to revert if validation fails

## Practical examples

- Prefer:
  - `python -m unittest tests/test_fastapi_analysis_endpoints.py -v`
  - `npm run build`
- Avoid during agent execution:
  - commands that open editors
  - commands waiting for password input
  - indefinite `watch`/tailing loops without a stop condition
