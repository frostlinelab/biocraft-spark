# Biocraft-Spark v0.1.0-beta

> ⚠️ **This is a beta release.** Expect bugs, missing features, and breaking changes before 1.0. Your feedback shapes the roadmap — see [How to Report Issues](#how-to-report-issues) below.

A local, cross-platform bioinformatics workbench for everyone — no Linux expertise required.

Biocraft-Spark wraps professional-grade tools inside a local web GUI backed by container isolation. Users define analysis pipelines as visual workflows; the runtime schedules and executes them in Docker containers, keeping data local and environments reproducible.

![Biocraft-Spark Dashboard](docs/assets/screenshot.png)

---

## Quick Start

```bash
git clone https://github.com/frostlinelab/biocraft-spark.git
cd biocraft-spark
./install.sh
```

Then open **http://127.0.0.1:25568** in your browser.

**Prerequisites:** Docker (Desktop, Engine, or OrbStack) running on the host. No Python or Node.js required — the Docker image is self-contained.

> `./install.sh --build` to build from source · `./install.sh --help` for all options.

---

## Key Features

### Visual Workflow Editor
- Drag-and-drop node editor powered by [React Flow](https://reactflow.dev/)
- Compose pipelines by connecting typed input/output ports between blocks
- Categorized block palette — drag blocks onto the canvas, configure params inline
- Auto-save with debounced API sync

### Container-Isolated Runtime
- Every tool runs inside a Docker container — no dependency conflicts, no environment pollution
- Docker-out-of-Docker: the backend mounts the host Docker socket to spawn sibling containers, no privilege escalation
- DAG scheduler with topological sort and parallel wave execution
- Automatic retry on container timeout

### Plugin System
- Plugins are YAML files that define one or more **blocks** (workflow nodes)
- Each block declares its container image, command, typed I/O ports, and configurable parameters
- JSON Schema validation ensures plugins are well-formed before loading
- Plugins auto-discovered from the `plugins/` directory

### Plugin Marketplace
- Browse a remote plugin catalog directly from the sidebar
- One-click install — backend downloads the manifest, verifies SHA-256, validates schema, persists to `plugins/`
- **Beautiful Creatures** — a curated selection of reviewed, certified plugins
- Marketplace registry lives in [biocraft-marketplace](https://github.com/frostlinelab/biocraft-marketplace), hosted on Cloudflare Pages

### Pipeline Management
- Create, edit, and delete multiple workflows
- 8-character hex workflow IDs (no sequential integer guessing)
- Run pipelines with one click — creates a tracked Task Run
- Step-by-step run progress with per-task status (running / success / failed / skipped)
- Per-task workspace view — inspect stdout, stderr, exit code, and output files
- Download result files directly from the task detail view

### Dashboard
- Aggregate stats at a glance: pipeline count, run count, success/fail breakdown
- Recent activity feed

---

## Architecture

```
Web Frontend (React + Vite)  →  Django App Layer  →  Core Runtime
                                                    ├── DAG Scheduler
                                                    ├── Container Executor (Docker)
                                                    └── Plugin Loader (YAML + JSON Schema)
                                                              ↓
                                                    SQLite · Volumes
```

The backend container mounts the host Docker socket so it can spin up sibling containers — Docker-out-of-Docker without privilege escalation. All data stays local.

**Tech stack:** React 19 · TypeScript · Vite · React Flow · Django 6 · Python 3.12 · Docker · SQLite

---

## What Ships in This Beta

| Component | Status |
|---|---|
| Container executor | ✅ Working |
| DAG scheduler (parallel waves) | ✅ Working |
| Plugin format (YAML + JSON Schema) | ✅ Working |
| Visual workflow editor | ✅ Working |
| Pipeline CRUD + auto-save | ✅ Working |
| Task run tracking + workspace | ✅ Working |
| Result file download | ✅ Working |
| Plugin Marketplace (browse / install / uninstall) | ✅ Working |
| Dashboard | ✅ Working |
| `install.sh` one-command setup | ✅ Working |
| Pre-built multi-arch Docker image (GHCR) | ✅ Working |
| FastQC plugin (via Marketplace) | ✅ Available |

---

## Known Limitations

- **No authentication** — the app is designed for local single-user use; do not expose the port to untrusted networks
- **No task queue** — pipelines run synchronously; long-running workflows block the server thread (async execution is planned for Phase 4)
- **No plugin versioning** — installing a plugin overwrites the previous version; no upgrade/migration path yet
- **Limited official plugins** — only FastQC is available in the Marketplace at this time; Prokka, Roary, and others are planned
- **macOS OrbStack** — Docker socket path differs from Docker Desktop; `install.sh` detects and warns, but you may need to adjust `docker-compose.yml` manually
- **No Windows testing** — the project targets macOS and Linux; Windows support is untested

---

## Roadmap

| Phase | Scope | Status |
|---|---|---|
| **1 — Core Runtime** | Container executor · DAG scheduler · Plugin format | ✅ Complete |
| **2 — UI & Pipeline** | Visual editor · REST API · SPA frontend · Task tracking | 🔄 In progress (this beta) |
| **3 — Plugin Ecosystem** | Marketplace · Official plugins · Plugin SDK | 🔄 In progress |
| **4 — Cloud / Business** | Remote execution · Task queue · Enterprise auth · Rust + Dioxus rebuild | ⏳ Planned |

---

## How to Report Issues

Found a bug? Have a feature request? Use our issue templates:

- [🐛 Bug Report](https://github.com/frostlinelab/biocraft-spark/issues/new?template=bug-report.yml) — something doesn't work as expected
- [🔌 Plugin Submission](https://github.com/frostlinelab/biocraft-spark/issues/new?template=plugin-submission.yml) — propose a new plugin for the Marketplace
- [✨ Beautiful Creatures Nomination](https://github.com/frostlinelab/biocraft-spark/issues/new?template=featured-plugin-nomination.yml) — nominate a plugin for curation
- [🛡️ Malicious Plugin Report](https://github.com/frostlinelab/biocraft-spark/issues/new?template=malicious-plugin-report.yml) — report a security concern

**Debug endpoints** (available when the server is running):

| Endpoint | What it checks |
|---|---|
| `GET /debug/ping-docker/` | Docker socket connectivity |
| `GET /debug/ping-executor/` | Can create & run a container |
| `GET /debug/ping-scheduler/` | DAG scheduling + parallelism |
| `GET /debug/ping-plugin/` | Plugin YAML schema validation |

Include the output of these endpoints in bug reports when relevant.

---

## Contributing

Biocraft-Spark is developed by **Frostline Lab**. See [CONTRIBUTING.md](https://github.com/frostlinelab/biocraft-spark/blob/main/CONTRIBUTING.md) for the plugin development guide and [docs/plugin-authoring.md](https://github.com/frostlinelab/biocraft-spark/blob/main/docs/plugin-authoring.md) for the complete plugin authoring reference.

## License

MIT License — Copyright © 2026 Frostline Lab
