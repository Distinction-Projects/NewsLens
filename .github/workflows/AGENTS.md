# Agent Guidance for `.github/workflows/`

## Scope
- CI/CD workflow behavior, especially droplet deployment.

## Current workflow
- `deploy-droplet.yml` deploys on push to `main` (and manual dispatch):
  - checkout
  - SSH key load
  - rsync to `/srv/newslens/app`
  - dependency refresh
  - `systemctl restart newslens`
  - health retry loop on `http://127.0.0.1:8000/`
- Pushes to `main` are the canonical auto-deploy trigger for the droplet.

## Guardrails
- Keep deploy steps idempotent and non-interactive.
- Prefer explicit timeouts/retries over single-shot health probes.
- If secrets/host assumptions change, update README deploy section in the same change.
