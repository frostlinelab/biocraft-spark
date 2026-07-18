// Biocraft-Spark — frontend API client
// Talks to the Django backend over HTTP (same-origin when served by Django).

export type RuntimeCheckKey = "docker" | "executor" | "scheduler" | "plugin"

export interface RuntimeCheckResult {
  key: RuntimeCheckKey
  label: string
  description: string
  ok: boolean
  detail: string
  latencyMs: number
  raw?: unknown
  error?: string
}

export interface PipelineSummary {
  id: number
  name: string
  description: string
  created_at: string
  updated_at: string
}

export interface PipelineDetail extends PipelineSummary {
  yaml_content: string
}

export interface TaskRunSummary {
  id: number
  pipeline_id: number
  pipeline_name: string
  status: "pending" | "running" | "succeeded" | "failed"
  started_at: string | null
  finished_at: string | null
  error_message: string
  created_at: string
}

export interface TaskRunDetail extends TaskRunSummary {
  result_json: unknown
}

export interface DashboardStats {
  pipelines_count: number
  task_runs_count: number
  recent_runs: TaskRunSummary[]
  status_breakdown: {
    pending: number
    running: number
    succeeded: number
    failed: number
  }
}

const DEFAULT_BASE = ""
const REQUEST_TIMEOUT_MS = 8000

export function getApiBase(): string {
  const fromEnv =
    (import.meta as unknown as { env?: Record<string, string | undefined> })
      .env?.VITE_BIOCRAFT_API_BASE
  return (fromEnv ?? DEFAULT_BASE).replace(/\/+$/, "")
}

// ── Generic fetch helpers ────────────────────────────────────────────────────

async function fetchJson(
  url: string,
  opts?: { method?: string; body?: unknown },
): Promise<{ status: number; data: unknown }> {
  const controller = new AbortController()
  const timer = setTimeout(() => controller.abort(), REQUEST_TIMEOUT_MS)
  try {
    const res = await fetch(url, {
      method: opts?.method ?? "GET",
      headers: {
        Accept: "application/json",
        ...(opts?.body != null ? { "Content-Type": "application/json" } : {}),
      },
      ...(opts?.body != null ? { body: JSON.stringify(opts.body) } : {}),
      signal: controller.signal,
    })
    let data: unknown = null
    try {
      data = await res.json()
    } catch {
      data = null
    }
    return { status: res.status, data }
  } finally {
    clearTimeout(timer)
  }
}

// ── Dashboard ────────────────────────────────────────────────────────────────

export async function fetchDashboardStats(): Promise<DashboardStats | null> {
  const base = getApiBase()
  try {
    const { status, data } = await fetchJson(base + "/api/dashboard-stats/")
    if (status !== 200) return null
    return data as DashboardStats
  } catch {
    return null
  }
}

// ── Pipelines ────────────────────────────────────────────────────────────────

export async function fetchPipelines(): Promise<PipelineSummary[]> {
  const base = getApiBase()
  try {
    const { status, data } = await fetchJson(base + "/api/pipelines/")
    if (status !== 200) return []
    return (data as { pipelines: PipelineSummary[] }).pipelines ?? []
  } catch {
    return []
  }
}

export async function fetchPipeline(id: number): Promise<PipelineDetail | null> {
  const base = getApiBase()
  try {
    const { status, data } = await fetchJson(base + `/api/pipelines/${id}/`)
    if (status !== 200) return null
    return data as PipelineDetail
  } catch {
    return null
  }
}

export async function createPipeline(body: {
  name: string
  description?: string
  yaml_content?: string
}): Promise<PipelineDetail | null> {
  const base = getApiBase()
  try {
    const { status, data } = await fetchJson(base + "/api/pipelines/create/", {
      method: "POST",
      body,
    })
    if (status !== 201) return null
    return data as PipelineDetail
  } catch {
    return null
  }
}

export async function savePipeline(
  id: number,
  body: { name?: string; description?: string; yaml_content?: string },
): Promise<PipelineDetail | null> {
  const base = getApiBase()
  try {
    const { status, data } = await fetchJson(base + `/api/pipelines/${id}/`, {
      method: "PUT",
      body,
    })
    if (status !== 200) return null
    return data as PipelineDetail
  } catch {
    return null
  }
}

export async function runPipeline(id: number): Promise<TaskRunDetail | null> {
  const base = getApiBase()
  try {
    const { status, data } = await fetchJson(base + `/api/pipelines/${id}/run/`, {
      method: "POST",
    })
    if (status !== 201) return null
    return data as TaskRunDetail
  } catch {
    return null
  }
}

// ── Task Runs ────────────────────────────────────────────────────────────────

export async function fetchTaskRuns(pipelineId?: number): Promise<TaskRunSummary[]> {
  const base = getApiBase()
  const qs = pipelineId != null ? `?pipeline_id=${pipelineId}` : ""
  try {
    const { status, data } = await fetchJson(base + `/api/task-runs/${qs}`)
    if (status !== 200) return []
    return (data as { task_runs: TaskRunSummary[] }).task_runs ?? []
  } catch {
    return []
  }
}

export async function fetchTaskRun(id: number): Promise<TaskRunDetail | null> {
  const base = getApiBase()
  try {
    const { status, data } = await fetchJson(base + `/api/task-runs/${id}/`)
    if (status !== 200) return null
    return data as TaskRunDetail
  } catch {
    return null
  }
}

// ── Runtime health (existing) ────────────────────────────────────────────────

type ParseResult = { ok: boolean; detail: string }

interface EndpointSpec {
  key: RuntimeCheckKey
  label: string
  description: string
  path: string
  parse: (status: number, data: unknown) => ParseResult
}

function asRecord(data: unknown): Record<string, unknown> {
  return data && typeof data === "object" ? (data as Record<string, unknown>) : {}
}

const ENDPOINTS: EndpointSpec[] = [
  {
    key: "docker",
    label: "Docker Socket",
    description: "Docker-out-of-Docker connectivity",
    path: "/debug/ping-docker/",
    parse: (status, data) => {
      const d = asRecord(data)
      const ok = status === 200 && d.docker === true
      const containers = d.containers ?? d.container_list
      const count = Array.isArray(containers) ? containers.length : undefined
      return { ok, detail: ok ? `Socket connected${count !== undefined ? ` · ${count} container${count === 1 ? "" : "s"}` : ""}` : "Cannot connect to host Docker socket" }
    },
  },
  {
    key: "executor",
    label: "Container Executor",
    description: "Run python:3.12-slim probe container",
    path: "/debug/ping-executor/",
    parse: (status, data) => {
      const d = asRecord(data)
      const exitCode = d.exit_code
      const ok = status === 200 && (exitCode === 0 || exitCode === undefined)
      return { ok, detail: ok ? "executor online" : `Container exit code ${String(exitCode ?? "unknown")}` }
    },
  },
  {
    key: "scheduler",
    label: "DAG Scheduler",
    description: "3-node DAG (A -> B, A -> C)",
    path: "/debug/ping-scheduler/",
    parse: (status, data) => {
      const d = asRecord(data)
      const ok = status === 200 && d.succeeded === true
      const nodes = d.nodes
      const count = Array.isArray(nodes) ? nodes.length : undefined
      return { ok, detail: ok ? `Topological sort + parallel wave passed${count !== undefined ? ` · ${count} node${count === 1 ? "" : "s"}` : ""}` : "Scheduler minimum loop failed" }
    },
  },
  {
    key: "plugin",
    label: "Plugin Loader",
    description: "YAML -> JSON Schema validation",
    path: "/debug/ping-plugin/",
    parse: (status, data) => {
      const d = asRecord(data)
      const ok = status === 200 && d.ok === true
      return { ok, detail: ok ? "Sample plugin validation passed" : "Plugin schema validation failed" }
    },
  },
]

async function runCheck(spec: EndpointSpec): Promise<RuntimeCheckResult> {
  const base = getApiBase()
  const started = performance.now()
  try {
    const { status, data } = await fetchJson(base + spec.path)
    const parsed = spec.parse(status, data)
    return { key: spec.key, label: spec.label, description: spec.description, ok: parsed.ok, detail: parsed.detail, latencyMs: Math.round(performance.now() - started), raw: data }
  } catch (err) {
    const isAbort = err instanceof DOMException && err.name === "AbortError"
    return { key: spec.key, label: spec.label, description: spec.description, ok: false, detail: isAbort ? "Request timed out" : "Backend unreachable", latencyMs: Math.round(performance.now() - started), error: err instanceof Error ? err.message : String(err) }
  }
}

export async function runAllChecks(): Promise<RuntimeCheckResult[]> {
  return Promise.all(ENDPOINTS.map(runCheck))
}

export const RUNTIME_ENDPOINTS = ENDPOINTS
