# Biocraft Spark — Frontend (Tauri Desktop)

React 19 + Vite 8 + Tauri 2 desktop app. The Tauri shell spawns the Django
backend automatically as a sidecar — you do **not** need Docker for local dev.

## Prerequisites

- Node.js + npm
- Rust toolchain (`rustc`, `cargo`)
- Python virtualenv at the repo root (`../.venv`) with backend deps installed:
  ```bash
  cd ..
  python -m venv .venv && source .venv/bin/activate
  pip install -r requirements.txt
  ```
- A running Docker engine (e.g. OrbStack) — only needed for the executor /
  docker features inside the app, not to start the backend.

## Run (development)

```bash
cd frontend
npm install
npm run tauri dev
```

This launches Vite on http://localhost:5173 and opens the native window.
On startup the Rust shell (`src-tauri/src/lib.rs`) spawns the Django backend:

```
../.venv/bin/python ../manage.py runserver 127.0.0.1:8000 --noreload
```

Because the sidecar uses `--noreload`, **changes to Python backend code require
restarting the app** (close the window and re-run `npm run tauri dev`).

The first `tauri dev` compiles ~350 Rust crates and can take several minutes.

## Build

```bash
npm run build          # type-check + vite build -> dist/
npm run tauri build    # bundle the desktop installer
```

## Web-only preview (no desktop shell)

```bash
npm run dev            # vite on http://localhost:5173
```

## Notes

- The root `docker-compose.yml` is an alternative way to run Django in a
  container (port 8000). Don't run it at the same time as the Tauri sidecar —
  they both bind 8000. Rebuild with `docker compose up --build` after changing
  `requirements.txt`.
