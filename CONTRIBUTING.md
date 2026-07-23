# Contributing to Biocraft-Spark

Plugin contributions are welcome! This guide covers the full plugin development workflow — from writing YAML to container image requirements.

> **📖 For the complete plugin development docs, see [docs/plugin-authoring.md](docs/plugin-authoring.md).**
> For the built-in blocks reference, see [docs/built-in-blocks.md](docs/built-in-blocks.md).

---

## Table of Contents

- [Quick Start](#quick-start)
- [Plugin YAML Format](#plugin-yaml-format)
- [Standard Container Paths](#standard-container-paths)
- [Input/Output Declarations](#inputoutput-declarations)
- [Complete Example: Prokka → Roary](#complete-example-prokka--roary)
- [Container Image Requirements](#container-image-requirements)
- [Retry Policy](#retry-policy)
- [Local Debugging](#local-debugging)

---

## Quick Start

A Biocraft plugin is just a **YAML file** describing an ordered set of container execution steps. The smallest plugin looks like this:

```yaml
name: hello-world
version: "0.1"
description: Minimal example
steps:
  - name: greet
    image: python:3.12-slim
    command: ["python", "-c", "print('Hello, Biocraft!')"]
```

Save it as `hello.yaml` and load it in Biocraft to run.

---

## Plugin YAML Format

### Top-level fields

| Field | Type | Required | Description |
|---|---|---|---|
| `name` | string | ✅ | Plugin name, unique identifier |
| `version` | string | ✅ | Semantic version, e.g. `"1.0.0"` |
| `description` | string | ❌ | One-line description of what the plugin does |
| `steps` | array | ✅ | List of steps, at least 1 |

### Step fields

| Field | Type | Required | Description |
|---|---|---|---|
| `name` | string | ✅ | Step name, unique within the plugin |
| `image` | string | ✅ | Docker image, e.g. `biocontainers/prokka:1.14.6` |
| `command` | array | ✅ | Container start command, in array form |
| `depends_on` | array | ❌ | List of prerequisite step names |
| `env` | object | ❌ | Environment variable key-value pairs |
| `inputs` | array | ❌ | Input file declarations (see below) |
| `outputs` | array | ❌ | Output file declarations (see below) |
| `retry` | object | ❌ | Retry policy |

---

## Standard Container Paths

**All plugin container commands must follow these path conventions:**

| Constant | In-container path | Purpose |
|---|---|---|
| `INPUT_DIR` | `/data/input` | Files filtered from upstream steps are mounted here |
| `OUTPUT_DIR` | `/data/output` | This step's outputs are written to this directory |
| `SHARED_DIR` | `/data/shared` | Pipeline-level shared data (e.g. reference genomes) |

```python
from biocraft_core import INPUT_DIR, OUTPUT_DIR, SHARED_DIR
```

**The rule is simple: read from `/data/input`, write to `/data/output`.** How files arrive and get routed — Biocraft handles that for you.

---

## Input/Output Declarations

This is Biocraft's most central capability: **plugins declare which files they need, and Biocraft filters and feeds them in.**

### Input declarations (`inputs`)

```yaml
inputs:
  - from: prokka           # Which upstream step to take from (omit = all upstream)
    pattern: "*.gff"       # File glob pattern
    type: file             # "file" or "directory", defaults to "file"
```

### Output declarations (`outputs`)

```yaml
outputs:
  - pattern: "*.gff"       # File pattern produced by this step
    type: file
  - pattern: "*.fna"
    type: file
```

### How it works

```
Prokka outputs:  .gff  .gbk  .fna  .faa  .ffn  .tbl  .tsv  .log ...
                       ↓
            Biocraft filters by Roary's inputs.pattern
                       ↓
Roary reads:     /data/input/*.gff   ← only .gff is mounted in
```

Plugin authors do not need to write any glue code for file copying, filtering, or renaming.

---

## Complete Example: Prokka → Roary

```yaml
name: prokka-roary-pipeline
version: "0.1"
description: Genome annotation → pan-genome analysis

steps:
  - name: prokka
    image: biocontainers/prokka:1.14.6
    command:
      - "prokka"
      - "--outdir"
      - "/data/output"
      - "--prefix"
      - "sample"
      - "/data/input/genome.fasta"
    outputs:
      - pattern: "*.gff"
        type: file
      - pattern: "*.fna"
        type: file
      - pattern: "*.faa"
        type: file

  - name: roary
    image: sangerpathogens/roary:latest
    command:
      - "roary"
      - "-f"
      - "/data/output"
      - "-e"
      - "--mafft"
      - "/data/input/*.gff"
    depends_on:
      - prokka
    inputs:
      - from: prokka
        pattern: "*.gff"
        type: file
    outputs:
      - pattern: "*"
        type: directory
```

> **Note:** Prokka produces 10+ file types, but Roary only needs `.gff`. By declaring `inputs.pattern: "*.gff"`, Biocraft filters automatically.

---

## Container Image Requirements

For Biocraft to run your steps correctly, container images must:

1. **Entry point compatible** — the image's default `ENTRYPOINT` must not block the `command` argument
2. **Path conventions** — read/write paths in commands use `/data/input` / `/data/output`
3. **Idempotency** — the same input should produce the same output across runs
4. **Exit codes** — `0` for success, non-`0` for failure
5. **Non-interactive** — no `prompt`, `tty`, or other logic requiring manual input

We recommend using official [BioContainers](https://biocontainers.pro/) images, which already meet these requirements.

---

## Retry Policy

```yaml
retry:
  max_attempts: 3       # Maximum execution attempts (including the first), default 1 (no retry)
  delay_seconds: 5.0    # Seconds between retries
```

Retries only happen on container execution failure (non-zero exit code). Once a step's retries are exhausted, all downstream steps that depend on it are skipped automatically.

---

## Local Debugging

Before submitting a plugin, you can validate the YAML format directly with Python:

```python
import io
from biocraft_core.plugin import load_plugin

yaml_text = """
name: my-plugin
version: "0.1"
steps:
  - name: test
    image: python:3.12-slim
    command: ["echo", "hello"]
"""

spec, nodes = load_plugin(io.StringIO(yaml_text))
print(f"✅ Plugin {spec.name} v{spec.version} validated")
print(f"   {len(nodes)} step(s) total")

for node in nodes:
    deps = ", ".join(node.depends_on) if node.depends_on else "none"
    print(f"   - {node.name} (depends on: {deps})")
```

You can also visit `/debug/ping-plugin/` after starting the Django dev server to validate plugin format.
