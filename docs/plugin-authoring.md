# Plugin Authoring Guide

> How to write plugins for Biocraft-Spark — from scratch to release.

---

## Table of Contents

- [Overview](#overview)
- [Quick Start](#quick-start)
- [Plugin YAML Format](#plugin-yaml-format)
- [Block Definition Reference](#block-definition-reference)
- [Port Type System](#port-type-system)
- [Connection Rules](#connection-rules)
- [Configuration Parameters](#configuration-parameters)
- [Container Path Conventions](#container-path-conventions)
- [Container Image Requirements](#container-image-requirements)
- [Complete Examples](#complete-examples)
- [Local Validation](#local-validation)
- [Backward Compatibility](#backward-compatibility)

---

## Overview

In Biocraft-Spark, **a plugin = a collection of blocks**. A single plugin YAML file can define one or more blocks, each corresponding to a node that can be dragged into the workflow editor.

**Core idea: plugin authors only need to declare "what inputs my tool needs, what outputs it produces, and how to run it." Biocraft handles file routing, container scheduling, and error retries.**

```
Plugin YAML  ──load──▶  Block registry  ──display──▶  Editor panel
                           │
                           ▼
                      User drags & assembles
                           │
                           ▼
                      DAG scheduled execution
```

---

## Quick Start

The smallest plugin contains a single block:

```yaml
name: hello-world
version: "0.1"
description: Minimal example plugin

blocks:
  - name: greet
    label: Hello
    description: Print a greeting
    icon: process

    runtime:
      image: python:3.12-slim
      command: ["python", "-c", "print('Hello, Biocraft!')"]
```

Save it as `hello-world.plugin.yaml` and place it in the `plugins/` directory. After starting Biocraft, the block will automatically appear in the editor's right-hand panel.

---

## Plugin YAML Format

### Top-level fields

| Field | Type | Required | Description |
|---|---|---|---|
| `name` | string | ✅ | Plugin package name, used as the category title in the panel. Use lowercase letters and hyphens, e.g. `my-bio-tools` |
| `version` | string | ✅ | Semantic version, e.g. `"1.0.0"` |
| `description` | string | ❌ | One-line description of the plugin's purpose |
| `icon` | string | ❌ | Category icon in the panel, defaults to `process`. See [icon list](#available-icons) |
| `blocks` | array | ✅ | List of blocks, at least 1 |

### Block fields (`blocks[]`)

| Field | Type | Required | Description |
|---|---|---|---|
| `name` | string | ✅ | Unique block identifier, must be unique within the plugin |
| `label` | string | ❌ | Display name in the panel, defaults to `name` |
| `description` | string | ❌ | Tooltip text on hover |
| `icon` | string | ❌ | Block icon, defaults to `process` |
| `runtime` | object | ❌ | Container execution config (a block without `runtime` is a pure control node) |
| `inputs` | array | ❌ | Input port list |
| `outputs` | array | ❌ | Output port list |
| `params` | array | ❌ | User-configurable parameter list |

### Runtime fields (`runtime`)

| Field | Type | Required | Description |
|---|---|---|---|
| `image` | string | ✅ | Docker image, e.g. `biocontainers/fastqc:v0.11.9_cv8` |
| `command` | string[] | ✅ | Container start command, in array form. Supports `${params.xxx}` to reference parameters. **Note:** Docker exec form does not expand `*`; use `sh -c "..."` when you need glob expansion |
| `env` | object | ❌ | Environment variable key-value pairs |
| `resources` | object | ❌ | Per-instance resource requirements: `min_threads` (default 1), `min_memory_gb` (default 1.0) |

---

## Block Definition Reference

### Inputs ports (`inputs[]`)

Each input port defines a connection point on the **left** side of a node:

```yaml
inputs:
  - name: reads           # Port ID (required)
    label: Sequencing files  # Port display name (optional, defaults to name)
    type: file            # Port type: file | directory | string | number | signal
    pattern: "*.fastq"    # File glob filter (only effective for file/directory types)
    multiple: true        # Whether multiple values are accepted (multi-file input)
```

### Outputs ports (`outputs[]`)

Each output port defines a connection point on the **right** side of a node:

```yaml
outputs:
  - name: report
    label: Quality report
    type: file
    pattern: "*.html"     # File pattern produced by this block
```

### Available icons

| Icon key | Shape | Use case |
|---|---|---|
| `start` | Circle | Workflow entry |
| `end` | Circle with bar | Workflow exit |
| `input` | Hexagon | Data input source |
| `output` | Hexagon | Data output sink |
| `process` | Rounded rectangle | General compute step |
| `condition` | Diamond | Branch / decision |
| `beaker` | Beaker | Experiment / analysis tool |
| `microscope` | Microscope | Quality control / inspection |
| `dna` | DNA double helix | Sequence analysis |
| `filter` | Funnel | Filtering |
| `wrench` | Wrench | Tool / conversion |
| `builtin` | Layered diamond | Built-in / system |

---

## Port Type System

| Type | Description | Connection rules |
|---|---|---|
| `file` | Single file | Can connect to `file`, `directory` ports; same type preferred |
| `directory` | Directory | Can connect to `directory` ports; can also accept `file` (file placed into directory) |
| `string` | Text value | Can connect to `string`, `number` (auto-converted) |
| `number` | Numeric value | Can connect to `number`; can also connect to `string` (must be parseable) |
| `signal` | Control signal | Only connects to `signal`; used for flow control like Start → End |

---

## Connection Rules

The editor validates port connections:

1. **Type compatibility** — only compatible port types can be connected (see table above)
2. **Direction match** — output port → input port
3. **Capacity check** — an input port with `multiple: false` accepts only one connection
4. **Cycle detection** — cycles are not allowed

---

## Configuration Parameters

Parameters are rendered as form controls in the editor's Node Inspector panel:

```yaml
params:
  - name: threads          # Parameter ID (required)
    label: Threads         # Form label (optional, defaults to name)
    type: integer          # Type: string | integer | float | boolean | select
    default: 4             # Default value
    min: 1                 # Minimum (integer/float)
    max: 32                # Maximum (integer/float)
    options: []            # Options list (required for select)

  - name: mode
    label: Run mode
    type: select
    default: "auto"
    options: ["auto", "fast", "sensitive"]
```

Reference parameter values in `runtime.command` with `${params.<name>}`:

```yaml
runtime:
  # Prefer sh -c when the command needs shell glob expansion
  command: ["sh", "-c", "fastqc -t ${params.threads} -o /data/output /data/input/*"]
```

---

## Resource Configuration

Plugin blocks can declare the CPU and memory resources each instance needs. Biocraft uses this information to compute parallelism (fan-out).

```yaml
runtime:
  image: biocontainers/prokka:1.14.6
  command: ["prokka", "--cpus", "${params.threads}", ...]
  resources:
    min_threads: 2        # Minimum threads per instance
    min_memory_gb: 4      # Minimum memory (GB) per instance
```

### Fan-out auto-parallelism

When an Input block provides N files and a downstream plugin declares `resources.min_threads`, Biocraft automatically computes the parallelism:

```
parallel instances = min(file count, global threads / plugin min threads)
```

**Example:** On an 8-core / 16-thread machine, Prokka declares `min_threads: 2`:
- 5 fasta files → 5 × 2 = 10 threads < 16 → **all 5 run in parallel**
- 50 fasta files → min(50, 16/2) = **8 in parallel**, executed in 7 waves

In the editor, the plugin node automatically expands to show fan-out lanes (fishbone structure), one lane per input file. Lanes are locked and aligned by Biocraft; users do not need to arrange them manually.

### Global resource pool

Configure in Django `settings.py`:

```python
BIOCRAFT_RUNTIME = {
    "cpu_cores": 8,
    "cpu_threads": 16,
    "memory_gb": 32,
    "max_parallel_containers": 8,
}
```

The frontend can fetch resource info via `GET /api/runtime-config/` to display resource badges in the editor.

---

## Container Path Conventions

**All block container commands must follow these path conventions:**

| Constant | In-container path | Purpose |
|---|---|---|
| `INPUT_DIR` | `/data/input` | Files filtered from upstream steps are mounted here |
| `OUTPUT_DIR` | `/data/output` | This step's outputs are written to this directory |
| `SHARED_DIR` | `/data/shared` | Workflow-level shared data (e.g. reference genomes) |

**Rule: read from `/data/input`, write to `/data/output`.** Biocraft handles file mounting and routing automatically.

---

## Container Image Requirements

1. **Entry point compatible** — the image's default `ENTRYPOINT` must not block the `command` argument
2. **Path conventions** — read/write paths in commands use `/data/input` / `/data/output`
3. **Idempotency** — the same input should produce the same output across runs
4. **Exit codes** — `0` for success, non-`0` for failure
5. **Non-interactive** — no `prompt`, `tty`, or other logic requiring manual input

We recommend official images from [BioContainers](https://biocontainers.pro/).

---

## Complete Examples

### Example 1: FastQC (single-block plugin, Marketplace launch plugin)

> The official file in the Marketplace: see the [biocraft-marketplace](https://github.com/frostlinelab/biocraft-marketplace) repo

```yaml
name: fastqc
version: "1.0.0"
description: Quality control for high-throughput sequencing reads
icon: microscope

blocks:
  - name: run-fastqc
    label: FastQC
    description: Run FastQC quality control on sequencing reads (FASTQ / FASTQ.GZ)
    icon: beaker

    runtime:
      image: biocontainers/fastqc:v0.11.9_cv8
      # Shell form so globs expand (Docker exec form does not expand *).
      command:
        - "sh"
        - "-c"
        - "fastqc -q -o /data/output -t ${params.threads} /data/input/*"
      resources:
        min_threads: 1
        min_memory_gb: 1.0

    inputs:
      - name: reads
        label: Sequencing Reads
        type: file
        pattern: "*.fastq*"
        multiple: true

    outputs:
      - name: report
        label: QC Report
        type: file
        pattern: "*_fastqc.html"
      - name: data
        label: QC Data
        type: file
        pattern: "*_fastqc.zip"

    params:
      - name: threads
        label: Threads
        type: integer
        default: 2
        min: 1
        max: 32
```

### Example 2: Trimmomatic (with multiple parameters)

```yaml
name: trimmomatic
version: "1.0.0"
description: Read trimming tool
icon: filter

blocks:
  - name: trim
    label: Trimmomatic
    description: Trim adapter sequences and low-quality bases
    icon: filter

    runtime:
      image: biocontainers/trimmomatic:v0.39
      command:
        - "trimmomatic"
        - "PE"
        - "-threads", "${params.threads}"
        - "/data/input/*_1.fastq"
        - "/data/input/*_2.fastq"
        - "/data/output/trimmed_1.fastq"
        - "/data/output/unpaired_1.fastq"
        - "/data/output/trimmed_2.fastq"
        - "/data/output/unpaired_2.fastq"
        - "${params.mode}:${params.window}:${params.quality}"
        - "MINLEN:${params.minlen}"

    inputs:
      - name: reads
        label: Paired Reads
        type: file
        pattern: "*.fastq"
        multiple: true

    outputs:
      - name: trimmed
        label: Trimmed Reads
        type: file
        pattern: "trimmed_*.fastq"

    params:
      - name: threads
        label: Threads
        type: integer
        default: 4
        min: 1
        max: 32
      - name: mode
        label: Trimming Mode
        type: select
        default: "SLIDINGWINDOW"
        options: ["SLIDINGWINDOW", "MAXINFO"]
      - name: window
        label: Window Size
        type: integer
        default: 4
        min: 1
        max: 20
      - name: quality
        label: Quality Threshold
        type: integer
        default: 20
        min: 0
        max: 40
      - name: minlen
        label: Min Read Length
        type: integer
        default: 36
        min: 1
        max: 1000
```

### Example 3: Multi-block plugin (toolkit)

```yaml
name: quality-toolkit
version: "1.0.0"
description: Sequencing quality control toolkit
icon: microscope

blocks:
  - name: fastqc
    label: FastQC
    description: Generate quality reports
    icon: beaker
    runtime:
      image: biocontainers/fastqc:v0.11.9_cv8
      command: ["fastqc", "-o", "/data/output", "/data/input/*.fastq"]
    inputs:
      - name: reads
        label: Reads
        type: file
        pattern: "*.fastq"
        multiple: true
    outputs:
      - name: report
        label: Report
        type: file
        pattern: "*.html"

  - name: multiqc
    label: MultiQC
    description: Aggregate multiple FastQC reports
    icon: beaker
    runtime:
      image: ewels/multiqc:v1.14
      command: ["multiqc", "-o", "/data/output", "/data/input/"]
    inputs:
      - name: reports
        label: QC Reports
        type: directory
        multiple: false
    outputs:
      - name: summary
        label: Summary Report
        type: file
        pattern: "multiqc_report.html"
```

---

## Local Validation

```python
from biocraft_core.plugin import discover_plugins

plugins = discover_plugins("plugins/")
for p in plugins:
    print(f"✅ {p.name} v{p.version} — {len(p.blocks)} block(s)")
    for b in p.blocks:
        ports_in = ", ".join(f"{t.name}:{t.port_type}" for t in b.inputs) or "none"
        ports_out = ", ".join(f"{t.name}:{t.port_type}" for t in b.outputs) or "none"
        print(f"   [{b.icon}] {b.label}")
        print(f"       image: {b.runtime.image if b.runtime else 'none'}")
        print(f"       in:  {ports_in}")
        print(f"       out: {ports_out}")
```

You can also start Django and visit `GET /api/blocks/` to view all loaded blocks.

---

## Backward Compatibility

The legacy format (using `steps:` to define a full pipeline) still loads fine:

```yaml
# Legacy format — still valid; each step is auto-converted to a BlockSpec
name: prokka-roary-pipeline
version: "0.1"
steps:
  - name: prokka
    image: biocontainers/prokka:1.14.6
    command: ["prokka", "--outdir", "/data/output", "/data/input/genome.fasta"]
    outputs:
      - pattern: "*.gff"
        type: file
```

Detection logic: has `blocks:` key → new format; has `steps:` key → legacy format, auto-converted; neither → skipped with a warning.

**New plugins are recommended to use the `blocks:` format** for full port, parameter, and icon support.
