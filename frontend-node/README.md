# NewsLens Node Frontend (Starter)

This folder is the initial Node.js frontend scaffold for the NewsLens split architecture.

It reads from the FastAPI backend routes:

- `GET /api/news/stats`
- `GET /api/news/digest`

## Migration status

- All legacy `/news/*` routes are now present in Next.js under `app/news/[slug]/page.js`.
- Live implementations currently shipped:
  - `/news/digest`
  - `/news/stats`
  - `/news/sources`
- Remaining routes are intentionally scaffolded placeholders for phased migration.

## Local run

From repo root, in one terminal:

```bash
source .venv/bin/activate
uvicorn src.api.fastapi_app:app --reload --port 9000
```

In a second terminal:

```bash
cd frontend-node
cp .env.example .env.local
npm install
npm run dev
```

Open:

- `http://localhost:3000/`
- `http://localhost:3000/news`

## E2E smoke test (Playwright)

From `frontend-node/` with the app running on port 3000:

```bash
npm run e2e:install-browsers
npm run e2e:smoke
```

Optional override:

```bash
PLAYWRIGHT_BASE_URL=http://localhost:3000 npm run e2e:smoke
```
