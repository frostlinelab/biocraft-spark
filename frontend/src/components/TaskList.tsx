// Biocraft-Spark — Task List page with filtering and detail panel

import { useCallback, useEffect, useState } from "react"
import {
  type TaskRunSummary,
  type TaskRunDetail,
  fetchTaskRuns,
  fetchTaskRun,
} from "../lib/api"
import "./TaskList.css"

type StatusFilter = "all" | "pending" | "running" | "succeeded" | "failed"

const STATUS_LABEL: Record<string, string> = {
  pending: "Pending",
  running: "Running",
  succeeded: "Succeeded",
  failed: "Failed",
}

const FILTERS: { key: StatusFilter; label: string }[] = [
  { key: "all", label: "All" },
  { key: "succeeded", label: "Succeeded" },
  { key: "running", label: "Running" },
  { key: "pending", label: "Pending" },
  { key: "failed", label: "Failed" },
]

function formatTime(iso: string | null): string {
  if (!iso) return "—"
  return new Date(iso).toLocaleString([], {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  })
}

function duration(start: string | null, end: string | null): string {
  if (!start || !end) return "—"
  const ms = new Date(end).getTime() - new Date(start).getTime()
  const s = Math.round(ms / 1000)
  if (s < 60) return `${s}s`
  return `${Math.floor(s / 60)}m ${s % 60}s`
}

export default function TaskList() {
  const [runs, setRuns] = useState<TaskRunSummary[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState("")
  const [filter, setFilter] = useState<StatusFilter>("all")
  const [selectedId, setSelectedId] = useState<number | null>(null)
  const [detail, setDetail] = useState<TaskRunDetail | null>(null)
  const [detailLoading, setDetailLoading] = useState(false)

  const load = useCallback(async () => {
    setLoading(true)
    setError("")
    const data = await fetchTaskRuns()
    if (data) {
      setRuns(data)
    } else {
      setError("Failed to load task runs")
    }
    setLoading(false)
  }, [])

  useEffect(() => {
    void load()
  }, [load])

  // Load detail when selectedId changes
  useEffect(() => {
    if (selectedId == null) {
      setDetail(null)
      return
    }
    let cancelled = false
    setDetailLoading(true)
    fetchTaskRun(selectedId).then((d) => {
      if (!cancelled) {
        setDetail(d)
        setDetailLoading(false)
      }
    })
    return () => { cancelled = true }
  }, [selectedId])

  const filtered =
    filter === "all" ? runs : runs.filter((r) => r.status === filter)

  const handleRowClick = (id: number) => {
    setSelectedId((prev) => (prev === id ? null : id))
  }

  return (
    <div className="bc-tasks">
      <header className="bc-tasks__head">
        <div>
          <h2 className="bc-tasks__title">Task Runs</h2>
          <p className="bc-tasks__subtitle">
            {runs.length} {runs.length === 1 ? "run" : "runs"} total
          </p>
        </div>
        <button className="bc-btn" onClick={() => void load()} disabled={loading}>
          {loading ? "Loading..." : "Refresh"}
        </button>
      </header>

      {/* Filter tabs */}
      <nav className="bc-tasks__filters">
        {FILTERS.map((f) => {
          const count = f.key === "all" ? runs.length : runs.filter((r) => r.status === f.key).length
          return (
            <button
              key={f.key}
              type="button"
              className={`bc-filter${f.key === filter ? " bc-filter--active" : ""}`}
              onClick={() => {
                setFilter(f.key)
                setSelectedId(null)
              }}
            >
              {f.label}
              <span className="bc-filter__count">{count}</span>
            </button>
          )
        })}
      </nav>

      {error ? (
        <div className="bc-tasks__error">
          <p>{error}</p>
          <button className="bc-btn" onClick={() => void load()}>Retry</button>
        </div>
      ) : loading ? (
        <div className="bc-tasks__loading">
          <div className="bc-tasks__skeleton">
            {Array.from({ length: 6 }).map((_, i) => (
              <div key={i} className="bc-skel-row" />
            ))}
          </div>
        </div>
      ) : (
        <div className="bc-tasks__table-wrap">
          {filtered.length === 0 ? (
            <p className="bc-tasks__empty">No runs to show.</p>
          ) : (
            <table className="bc-table">
              <thead>
                <tr className="bc-table__row">
                  <th className="bc-table__head">ID</th>
                  <th className="bc-table__head">Pipeline</th>
                  <th className="bc-table__head">Status</th>
                  <th className="bc-table__head">Duration</th>
                  <th className="bc-table__head">Created</th>
                </tr>
              </thead>
              <tbody>
                {filtered.map((r) => {
                  const isSelected = r.id === selectedId
                  return (
                    <>
                      <tr
                        key={r.id}
                        className={`bc-table__row bc-table__row--clickable${isSelected ? " bc-table__row--selected" : ""}`}
                        onClick={() => handleRowClick(r.id)}
                      >
                        <td className="bc-table__cell bc-table__cell--id">
                          <span className="bc-mono">#{r.id}</span>
                        </td>
                        <td className="bc-table__cell">{r.pipeline_name}</td>
                        <td className="bc-table__cell">
                          <span className={`bc-badge bc-badge--${r.status}`}>
                            {STATUS_LABEL[r.status] ?? r.status}
                          </span>
                        </td>
                        <td className="bc-table__cell bc-table__cell--time">
                          {duration(r.started_at, r.finished_at)}
                        </td>
                        <td className="bc-table__cell bc-table__cell--time">
                          {formatTime(r.created_at)}
                        </td>
                      </tr>
                      {isSelected && (
                        <tr key={`${r.id}-detail`} className="bc-table__row">
                          <td colSpan={5} className="bc-table__cell">
                            <DetailPanel detail={detail} loading={detailLoading} />
                          </td>
                        </tr>
                      )}
                    </>
                  )
                })}
              </tbody>
            </table>
          )}
        </div>
      )}
    </div>
  )
}

function DetailPanel({
  detail,
  loading,
}: {
  detail: TaskRunDetail | null
  loading: boolean
}) {
  if (loading) {
    return <div className="bc-detail bc-detail--loading">Loading details...</div>
  }
  const d = detail
  if (!d) {
    return <div className="bc-detail bc-detail--error">Failed to load detail.</div>
  }

  return (
    <div className="bc-detail">
      <div className="bc-detail__grid">
        <DetailItem label="Status" value={<span className={`bc-badge bc-badge--${d.status}`}>{STATUS_LABEL[d.status]}</span>} />
        <DetailItem label="Pipeline" value={d.pipeline_name} />
        <DetailItem label="Started" value={formatTime(d.started_at)} />
        <DetailItem label="Finished" value={formatTime(d.finished_at)} />
        <DetailItem label="Duration" value={duration(d.started_at, d.finished_at)} />
        <DetailItem label="Created" value={formatTime(d.created_at)} />
      </div>

      {d.error_message && (
        <div className="bc-detail__error">
          <h4 className="bc-detail__section-title">Error</h4>
          <pre className="bc-detail__pre">{d.error_message}</pre>
        </div>
      )}

      {d.result_json != null && (
        <div className="bc-detail__result">
          <h4 className="bc-detail__section-title">Result</h4>
          {"nodes" in (d.result_json as Record<string, unknown>) ? (
            <div className="bc-detail__steps">
              {((d.result_json as Record<string, unknown>).nodes as Array<Record<string, unknown>>)?.map(
                (node: Record<string, unknown>, i: number) => {
                  const step = node.step as number
                  const total = node.total as number
                  const label = node.label as string ?? `Node ${step}`
                  const nodeStatus = node.status as string ?? "unknown"
                  return (
                    <div key={i} className="bc-step">
                      <span className={`bc-step__badge bc-step__badge--${nodeStatus}`}>
                        {nodeStatus === "completed" ? "✓" : nodeStatus === "running" ? "⟳" : "?"}
                      </span>
                      <span className="bc-step__label">{label}</span>
                      <span className="bc-step__pos">
                        Step {step}/{total}
                      </span>
                    </div>
                  )
                }
              )}
            </div>
          ) : (
            <pre className="bc-detail__pre">{JSON.stringify(d.result_json, null, 2)}</pre>
          )}
        </div>
      )}
    </div>
  )
}

function DetailItem({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div className="bc-detail__item">
      <dt className="bc-detail__dt">{label}</dt>
      <dd className="bc-detail__dd">{value}</dd>
    </div>
  )
}
