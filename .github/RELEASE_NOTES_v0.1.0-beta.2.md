# Biocraft-Spark v0.1.0-beta.2

> ⚠️ **Beta release.** Expect bugs and breaking changes before 1.0.

The second beta — focused on a frictionless install and a fix for the first-run database issue reported against Beta1.

## Highlights

### One-line install — no git, Xcode, or Docker required

```bash
curl -fsSL https://raw.githubusercontent.com/frostlinelab/biocraft-spark/main/install.sh | bash
```

- **Linux** auto-installs Docker Engine if absent.
- **macOS** auto-installs and launches **OrbStack** (works even without Homebrew, Xcode/CLT, or git), polling until its socket is ready.
- Fetches only `docker-compose.standalone.yml` — no repo clone needed.

### Fixed: Dashboard / Marketplace failing on first run

In Beta1, `install.sh` created an empty `db.sqlite3` and never ran migrations, so DB-backed endpoints (Dashboard, Marketplace) returned HTTP 500 while Health stayed green. Beta2 adds a container **entrypoint** that runs `manage.py migrate` on every start; `install.sh` also self-heals by re-migrating if `/api/dashboard-stats/` doesn't return 200.

### Docker socket parameterized

`docker-compose.yml` now uses `${DOCKER_SOCK:-/var/run/docker.sock}`, so macOS (OrbStack) and Linux work from the same file. `install.sh` auto-detects the socket — no manual path edits.

### Documentation

- New plain-language **Get Started** for non-developers; removed the verbose dev-setup stages and the Roadmap.
- All documentation translated to English.

## Install / Upgrade

```bash
curl -fsSL https://raw.githubusercontent.com/frostlinelab/biocraft-spark/main/install.sh | bash
```

Open **http://127.0.0.1:25568** (or the printed LAN URL). Existing Beta1 installs: re-run the command to pull the new `:latest` image, then `./install.sh restart`.

## Marketplace

**FastQC** and **Prokka** are available via the in-app Marketplace.

## Known Limitations

- No authentication — local single-user use only; don't expose the port to untrusted networks.
- No task queue — pipelines run synchronously.
- No plugin versioning — installing overwrites the previous version.
- No Windows testing — macOS and Linux only.

## Reporting Issues

Use the issue templates: [Bug Report](https://github.com/frostlinelab/biocraft-spark/issues/new?template=bug-report.yml), [Plugin Submission](https://github.com/frostlinelab/biocraft-spark/issues/new?template=plugin-submission.yml).

---

MIT License — Copyright © 2026 Frostline Lab
