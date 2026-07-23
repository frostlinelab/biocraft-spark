# Runtime Configuration Guide

> Configure Biocraft-Spark's global CPU/memory resource pool.

---

## Overview

Biocraft-Spark needs a global resource pool to decide the parallelism (fan-out) of plugin blocks. The user tells the system their machine's CPU core count, thread count, and memory, and the system computes:

- How many instances of each plugin block can run in parallel
- When the number of input files exceeds the parallel limit, how many waves to split execution into

---

## Configuration Location

In `biocraft_spark/settings.py`:

```python
BIOCRAFT_RUNTIME = {
    "cpu_cores": 8,              # CPU physical core count
    "cpu_threads": 16,            # CPU logical thread count (incl. hyperthreading)
    "memory_gb": 32,              # Available memory (GB)
    "max_parallel_containers": 8, # Upper bound on simultaneously running containers
}
```

---

## Configuration Items

| Setting | Type | Default | Description |
|---|---|---|---|
| `cpu_cores` | int | 4 | CPU physical core count, used for frontend display |
| `cpu_threads` | int | 8 | Logical thread count, **determines parallelism** |
| `memory_gb` | int | 8 | Total available memory (GB) |
| `max_parallel_containers` | int | 8 | Hard limit: regardless of CPU idle time, the maximum number of containers running at once |

---

## Parallelism Calculation

```
parallel instances = min(file count, cpu_threads / plugin min threads, max_parallel_containers)
```

### Examples

**Machine:** 8 cores / 16 threads, 32 GB, max 8 containers

**Prokka plugin** (`min_threads: 2`):

| Input files | Calculation | Result |
|---|---|---|
| 5 | min(5, 16/2, 8) | **5 parallel** |
| 10 | min(10, 8, 8) | **8 parallel** (CPU-limited) |
| 50 | min(50, 8, 8) | **8 parallel**, in 7 waves |

**FastQC plugin** (`min_threads: 1`):

| Input files | Calculation | Result |
|---|---|---|
| 10 | min(10, 16/1, 8) | **8 parallel** (container-limit-limited) |
| 5 | min(5, 16, 8) | **5 parallel** |

---

## Frontend Retrieval

The frontend fetches the runtime config via API:

```
GET /api/runtime-config/
```

```json
{
  "cpuCores": 8,
  "cpuThreads": 16,
  "memoryGb": 32,
  "maxParallelContainers": 8
}
```

Plugin nodes in the editor display a resource badge:

```
Prokka [5 files · 10 threads / 16 available]
```

---

## Viewing the Actual Config

```bash
curl http://127.0.0.1:8000/api/runtime-config/ | python -m json.tool
```
