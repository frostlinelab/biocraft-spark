# Biocraft Spark — Frontend (Web)

React 19 + Vite 8 single-page app. The production bundle is built to `dist/`
and served by the Django backend as static files, so the API and the SPA share
the same origin.

## Prerequisites

- Node.js 20+ and npm
- A running Django backend (see the root `docker-compose.yml` or
  `python manage.py runserver`). The backend serves the built SPA and provides
  the REST API consumed by `src/lib/api.ts`.

## Build (production)

```bash
cd frontend
npm install
npm run build      # tsc -b + vite build → dist/
```

Django serves `dist/index.html` at `/` and the asset bundle under
`/static/`. With the Docker backend running, the app is available at
`http://127.0.0.1:25568/`. Re-run `npm run build` after frontend changes.

## Development (hot-reload)

```bash
cd frontend
npm install
VITE_BIOCRAFT_API_BASE=http://localhost:25568 npm run dev
```

Vite serves the SPA on `http://localhost:5173` with HMR. The
`VITE_BIOCRAFT_API_BASE` env var tells the API client where the Django backend
lives; without it the client assumes same-origin (which only holds when Django
serves the built bundle).

## Notes

- `getApiBase()` in `src/lib/api.ts` returns `VITE_BIOCRAFT_API_BASE` with
  trailing slashes stripped, or `""` (same-origin) when unset.
- Vite is configured with `base: '/static/'` so the built `index.html` emits
  asset URLs under `/static/...`, matching Django's `STATIC_URL = 'static/'`.
- The root `docker-compose.yml` runs Django in a container on port `25568`.
