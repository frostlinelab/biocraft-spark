# Troubleshooting Guide

Common issues and solutions for Biocraft-Spark.

---

## Table of Contents

- [Container Runtime (Required)](#container-runtime-required)
- [Database & Startup](#database--startup)
- [Docker](#docker)
- [Container Execution](#container-execution)
- [Plugin Loading](#plugin-loading)
- [Scheduler](#scheduler)
- [Diagnostic Endpoints](#diagnostic-endpoints)

---

## Container Runtime (Required)

> **Biocraft-Spark requires a container runtime to run.** Without one, workflows cannot execute and the app is unusable.

### macOS: OrbStack is required

The recommended runtime on macOS — and the one the install script auto-installs — is **OrbStack** (Docker Desktop also works, but the script will not override it if already present).

`install.sh` behavior on macOS:

1. If `/Applications/OrbStack.app` already exists → launch it directly.
2. Otherwise, if Homebrew is installed → `brew install --cask orbstack`.
3. Otherwise (**works without Homebrew, Xcode/CLT, or git**) → resolve the latest `.dmg` from the Homebrew cask API, download it, mount, and copy to `/Applications`.
4. `open -a OrbStack` to launch; the first launch requires approving permissions in the GUI. The script polls `docker info` every 5s until ready (**no fixed timeout, so slower machines will still get there**), printing a progress heartbeat every 15s. If the OrbStack process exits or fails to start within 60s, it errors out early rather than hanging forever.
5. Best-effort adds OrbStack to login items via `osascript` for **auto-start at login**.

**Auto-start at login not working?** The `osascript` step may be denied by the system's automation permissions. Enable it manually: open OrbStack → Settings → check "Start OrbStack at login" (or confirm OrbStack is listed under System Settings → General → Login Items).

### Linux: auto-install Docker Engine

When Docker is absent, `install.sh` installs Docker Engine via `get.docker.com`, runs `systemctl enable --now docker`, and adds the current user to the `docker` group.

> Joining the `docker` group **does not take effect in the current shell**. The install script uses `sudo` to call docker in this session; to let a normal user run docker without sudo, **log out and back in** (or run `newgrp docker` immediately).

---

## Database & Startup

### Dashboard / Marketplace error, but Health is all green

Symptom: all four Health checks are green, but the Dashboard shows "Failed to load dashboard data" and the Marketplace shows "Failed to load marketplace catalog".

**Cause:** The four Health endpoints (`/debug/ping-*`) do not query the database, while the Dashboard (`/api/dashboard-stats/`) and the Marketplace (`/api/marketplace/catalog/`) both query SQLite. If the database tables are not created, the DB-backed endpoints return 500 while Health stays green.

**Fix:** The Beta2 container entry point runs `python manage.py migrate` automatically on every start, so manual action is normally unnecessary. If you are using an older image or the entry point is bypassed, migrate manually:

```bash
cd ~/.biocraft-spark            # or cd to the repo dir for a repo install
./install.sh restart            # restart triggers the entry point auto-migrate
# if that still fails, run it explicitly:
docker compose -f docker-compose.standalone.yml exec web python manage.py migrate
```

> The Marketplace also requires the container to have outbound access to `https://biocraft-marketplace.pages.dev` (Cloudflare Pages). If the Marketplace still returns 502 "Marketplace registry unreachable" after migrating, check the container's outbound connectivity:
> ```bash
> docker compose -f docker-compose.standalone.yml exec web \
>   curl -sI https://biocraft-marketplace.pages.dev/index.json
> ```

---

## Docker

### `Docker SDK is not installed`

```
DockerUnavailableError: Docker SDK is not installed. Run: pip install docker
```

**Cause:** The Docker SDK is not installed in the Python environment.

**Fix:**

```bash
pip install docker
```

---

### `Docker daemon is unavailable`

```
DockerUnavailableError: Docker daemon is unavailable. Check Docker socket mount.
```

**Cause:** The Docker daemon is not running, or the socket is not mounted correctly.

**Fix:**

1. Confirm Docker is running:
   ```bash
   docker info
   ```

2. If you started Biocraft with Docker Compose, confirm the socket is mounted in `docker-compose.yml`:
   ```yaml
   volumes:
     - /var/run/docker.sock:/var/run/docker.sock
   ```

3. Visit `/debug/ping-docker/` to verify connectivity.

---

### macOS: Docker socket path differs

Different runtimes use different socket paths:

```
/var/run/docker.sock                       # Docker Desktop / Linux
/Users/<user>/.orbstack/run/docker.sock    # OrbStack
```

`install.sh` auto-detects the socket and exports `DOCKER_SOCK`; both
`docker-compose.yml` and `docker-compose.standalone.yml` reference it via
`${DOCKER_SOCK:-/var/run/docker.sock}`, so **you normally do not need to
change the mount path manually**.

If you run `docker compose up` manually and the socket is not at the default
location, specify it explicitly:

```bash
export DOCKER_SOCK="$HOME/.orbstack/run/docker.sock"
docker compose -f docker-compose.standalone.yml up -d
```

---

## Container Execution

### Container timeout

```
ContainerTimeoutError: Container exceeded timeout: 3600s
```

**Cause:** The container ran longer than the configured timeout (default 1 hour).

**Fix:**

1. Check whether the input data is too large
2. No special config needed in the plugin YAML — the Biocraft scheduler retries automatically
3. For large analyses, contact the developers to adjust the default timeout

---

### `Failed to pull image`

```
ContainerRunError: Failed to pull image: biocontainers/prokka:1.14.6
```

**Cause:** The image pull failed.

**Fix:**

1. Check your network connection
2. Confirm the image name and tag are correct:
   ```bash
   docker pull biocontainers/prokka:1.14.6
   ```
3. If using a private registry, make sure you are logged in:
   ```bash
   docker login
   ```

---

### Non-zero container exit code

```
Container exited with code 1
```

**Cause:** The tool itself failed.

**Fix:**

1. Inspect the `stderr` output to pinpoint the error
2. Common causes:
   - Wrong input file path (check that you used `/data/input` / `/data/output`)
   - Incorrect input file format
   - Incorrect tool parameters
3. You can run the container manually to debug:
   ```bash
   docker run --rm -v $(pwd)/data:/data/input biocontainers/prokka:1.14.6 \
     prokka --outdir /data/output /data/input/genome.fasta
   ```

---

## Plugin Loading

### Schema validation failure

```
jsonschema.exceptions.ValidationError: 'steps' is a required property
```

**Cause:** The plugin YAML does not conform to the schema.

**Fix:**

1. Confirm the top level has the three required fields `name`, `version`, `steps`
2. Each step must have `name`, `image`, `command`
3. `command` must be an array, not a string:
   ```yaml
   # ✅ Correct
   command: ["prokka", "--outdir", "/data/output", "/data/input/genome.fasta"]

   # ❌ Wrong
   command: "prokka --outdir /data/output /data/input/genome.fasta"
   ```
4. Pre-validate with `/debug/ping-plugin/` or a local Python script:
   ```python
   from biocraft_core.plugin import load_plugin
   load_plugin("my-plugin.yaml")
   ```

---

### Circular dependency

```
DAGCycleError: Cycle detected involving: ['step-b', 'step-a']
```

**Cause:** `depends_on` between steps forms a cycle.

**Fix:** Review all `depends_on` references and ensure the graph is a directed acyclic graph (DAG). For example:

```yaml
# ❌ Circular dependency
steps:
  - name: step-a
    depends_on: ["step-b"]
  - name: step-b
    depends_on: ["step-a"]
```

---

### Depends on a non-existent step

```
MissingDependencyError: Task 'roary' depends on unknown task 'prokka'
```

**Cause:** `depends_on` or `inputs.from` references a step name that does not exist.

**Fix:** Check the step name spelling and confirm the referenced step is defined in the same plugin YAML.

---

### Duplicate step name

```
DuplicateTaskError: Duplicate task name: 'step-a'
```

**Cause:** Two steps in the same plugin share the same `name`.

**Fix:** Ensure each step's `name` is unique within the plugin.

---

## Scheduler

### All downstream steps SKIPPED

```
TaskStatus.SKIPPED
```

**Cause:** An upstream step failed, so all steps depending on it were skipped.

**Fix:** Locate and fix the first failed step. Inspect its `stderr` and `exit_code`.

---

## Diagnostic Endpoints

In development mode, the following endpoints help pinpoint problems:

| Endpoint | Checks |
|---|---|
| `GET /debug/ping-docker/` | Docker socket connectivity + container list |
| `GET /debug/ping-executor/` | Whether a container can be created and run successfully |
| `GET /debug/ping-scheduler/` | DAG scheduler topological sort + parallel execution |
| `GET /debug/ping-plugin/` | Plugin YAML format validation |

If all return `"ok": true`, all four layers of the Core Runtime are healthy.
