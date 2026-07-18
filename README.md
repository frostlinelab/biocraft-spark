# Biocraft-Spark

> A local, cross-platform bioinformatics workbench for everyone — no Linux expertise required.

Biocraft-Spark lowers the barrier to bioinformatics by wrapping professional-grade tools inside a desktop GUI backed by container isolation. Users define analysis pipelines as visual workflows; the runtime schedules and executes them in Docker/Podman containers, keeping data local and environments reproducible.

**Status:** Phase 1 (Core Runtime) ✅ complete — Phase 2 (UI & Pipeline) 🔄 in progress.

---

## Table of Contents

- [Overview](#overview)
- [Architecture](#architecture)
- [Tech Stack](#tech-stack)
- [Prerequisites](#prerequisites)
- [Getting Started](#getting-started)
- [Project Structure](#project-structure)
- [Plugin Format](#plugin-format)
- [Debug Endpoints](#debug-endpoints)
- [API Endpoints](#api-endpoints)
- [Roadmap](#roadmap)
- [Documentation](#documentation)

---

## Overview

Biocraft-Spark is built around three ideas:

1. **Local-first** — all computation runs on your machine; no data leaves your environment.
2. **Container-isolated** — every tool runs inside a Docker/Podman container, eliminating dependency conflicts.
3. **Visual workflow editor** — pipelines are built with a drag-and-drop node editor backed by React Flow, making it easy to compose and reconfigure analysis steps without writing code.

The desktop GUI (Tauri + React) talks to a Django backend over `localhost:8000`. The backend owns the execution engine: a DAG scheduler that topologically sorts pipeline steps and runs independent steps in parallel waves.

---

## Architecture

```
┌─────────────────────────────────────────────┐
│          Desktop Frontend (Tauri + React)   │
│          Communicates via HTTP localhost    │
└──────────────────┬──────────────────────────┘
                   │
┌──────────────────▼──────────────────────────┐
│          Django App Layer                   │
│          REST API · Workbench views         │
└──────────────────┬──────────────────────────┘
                   │
┌──────────────────▼──────────────────────────┐
│          Core Runtime (biocraft_core/)      │
│  ┌─────────────┐  ┌──────────────────────┐  │
│  │ DAG         │  │ Container Executor   │  │
│  │ Scheduler   │→ │ (Docker out-of-      │  │
│  │             │  │  Docker via socket)  │  │
│  └─────────────┘  └──────────────────────┘  │
│  ┌──────────────────────────────────────┐   │
│  │ Plugin Loader  (YAML + JSON Schema)  │   │
│  └──────────────────────────────────────┘   │
└──────────────────┬──────────────────────────┘
                   │
┌──────────────────▼──────────────────────────┐
│          Data Layer  (SQLite · volumes)     │
└─────────────────────────────────────────────┘
```

The backend container mounts the host Docker socket (`/var/run/docker.sock`) so it can spin up sibling containers — Docker-out-of-Docker without privilege escalation.

---

## Tech Stack

| Layer | Technology |
|---|---|
| Desktop frontend | Tauri 2.11 · React 19 · TypeScript 6 · Vite 8 |
| Workflow editor | @xyflow/react (React Flow) 12.x — drag-and-drop node editor |
| Backend framework | Django 6.0.4 · Python |
| Container runtime | Docker ≥ 7.0 (docker-py SDK) |
| DAG scheduling | Custom (`biocraft_core/runtime/scheduler/`) |
| Plugin format | YAML + JSON Schema (jsonschema ≥ 4.0) |
| Database | SQLite 3 |
| Orchestration | Docker Compose |

---

## Prerequisites

- **Docker** (Desktop, Engine, or OrbStack) running on the host
- **Python 3.12+** (for running outside Docker)
- **Node.js 20+** and **Rust** (for building the desktop frontend)
- **Tauri CLI** — installed automatically via `npm install` inside `frontend/`

---

## Getting Started

### 1. Backend (Docker Compose — recommended)

```bash
# Build and start the Django backend
docker compose build --no-cache web
docker compose up
```

The Django server starts at `http://127.0.0.1:8000`. The Docker socket is mounted automatically so the runtime can execute containers.

### 2. Backend (local venv — alternative)

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python manage.py migrate
python manage.py runserver
```

### 3. Desktop Frontend (development mode)

```bash
cd frontend
npm install

# Run the Tauri dev window (spawns the React dev server + native window)
npm run tauri dev
```

The Tauri window connects to the Django backend at `127.0.0.1:8000`. Start the backend first.

> **Tip:** The `frontend/` folder also has its own [README](frontend/README.md) with Tauri-specific notes.

---

## Project Structure

```
biocraft-spark/
├── biocraft_core/          # Core runtime — no Django dependency
│   ├── runtime/
│   │   ├── executor/       # DockerExecutor, types, errors
│   │   └── scheduler/      # DAG, Engine (topological sort + parallel waves)
│   └── plugin/             # YAML loader, JSON Schema validator
├── biocraft_spark/         # Django project config (settings, urls, wsgi/asgi)
├── workbench/              # Django app — views, models, API, middleware
├── templates/              # Django HTML templates
├── frontend/               # Tauri 2 + Vite + React desktop app
│   ├── src/                # React components
│   │   ├── components/     # AppLayout, Sidebar, Dashboard, WorkflowCanvas, ...
│   │   └── lib/            # API client
│   └── src-tauri/          # Rust Tauri shell
├── docs/                   # Troubleshooting guide
├── CONTRIBUTING.md         # Plugin development guide
├── docker-compose.yml
├── Dockerfile
├── requirements.txt
└── manage.py
```

---

## Plugin Format

Plugins are YAML files that define one or more **blocks** (draggable workflow nodes). Each block declares its container runtime, typed input/output ports, and configurable parameters. Biocraft automatically discovers plugins in the `plugins/` directory and surfaces them as categorized blocks in the workflow editor.

```yaml
name: fastqc
version: "1.0.0"
description: Quality control for sequencing reads
steps:
  - name: run-fastqc
    image: biocontainers/fastqc:v0.11.9
    command: ["fastqc", "-o", "/data/output", "/data/input/*.fastq"]
    inputs:
      - pattern: "*.fastq"
        type: file
    outputs:
      - pattern: "*.html"
        type: file
      - pattern: "*.zip"
        type: file
```

> See [CONTRIBUTING.md](CONTRIBUTING.md) for the plugin development guide and [docs/plugin-authoring.md](docs/plugin-authoring.md) for the complete plugin authoring reference.

---

## Debug Endpoints

These endpoints are available in development to verify each runtime layer independently:

| Endpoint | What it checks |
|---|---|
| `GET /debug/ping-docker/` | Docker socket connectivity + container list |
| `GET /debug/ping-executor/` | Runs a `python:3.12-slim` container; expects `exit_code: 0` |
| `GET /debug/ping-scheduler/` | Runs a 3-node DAG (A → B, A → C); verifies ordering and parallelism |
| `GET /debug/ping-plugin/` | Loads a sample plugin YAML and validates its schema |

---

## API Endpoints

REST API for the workflow frontend:

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/api/dashboard-stats/` | Aggregate stats (pipeline count, run count, status breakdown) |
| `GET` | `/api/pipelines/` | List all pipelines |
| `POST` | `/api/pipelines/create/` | Create a new pipeline |
| `GET` | `/api/pipelines/<id>/` | Get a single pipeline |
| `PUT` | `/api/pipelines/<id>/` | Update a pipeline (name, description, graph) |
| `DELETE` | `/api/pipelines/<id>/` | Delete a pipeline |
| `POST` | `/api/pipelines/<id>/run/` | Execute a pipeline (creates a TaskRun) |
| `GET` | `/api/task-runs/` | List task runs (optional `?pipeline_id=` filter) |
| `GET` | `/api/task-runs/<id>/` | Get a single task run with results |

---

## Roadmap

| Phase | Scope | Status |
|---|---|---|
| **1 — Core Runtime** | Container executor · DAG scheduler · Retry policy · Plugin format (YAML + JSON Schema) | ✅ Complete |
| **2 — Django UI & Pipeline** | Django REST API · Visual workflow editor (React Flow) · Tauri desktop integration · Multi-workflow management · Task run tracking | 🔄 In progress |
| **3 — Plugin Ecosystem** | Plugin SDK · Official plugins (Prokka, Roary, …) · Plugin marketplace | ⏳ Planned |
| **4 — Cloud / Business** | Remote execution · Task queue · Enterprise auth · Cloud rebuild (Rust + Dioxus post-1.0) | ⏳ Planned |

---

## Documentation

| Document | Description |
|---|---|
| [CONTRIBUTING.md](CONTRIBUTING.md) | Plugin development guide — YAML format, IO routing, container specs |
| [docs/plugin-authoring.md](docs/plugin-authoring.md) | Complete plugin authoring reference — block definition, port types, params, resources, examples |
| [docs/built-in-blocks.md](docs/built-in-blocks.md) | Built-in block reference — Start, End, Input |
| [docs/runtime-config.md](docs/runtime-config.md) | CPU/memory resource pool configuration |
| [docs/troubleshooting.md](docs/troubleshooting.md) | Common issues — Docker, timeouts, schema validation, scheduler |

## Contributing

This project is developed by **Frostline Lab**. See [CONTRIBUTING.md](CONTRIBUTING.md) for the plugin development guide.

---

## License

MIT License

Copyright (c) 2026 Frostline Lab

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
