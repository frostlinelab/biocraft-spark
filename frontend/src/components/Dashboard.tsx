// Biocraft-Spark — Dashboard with stats overview + recent task runs

import { useEffect, useState } from "react"
import {
  type DashboardStats,
  type TaskRunSummary,
  fetchDashboardStats,
} from "../lib/api"
import "./Dashboard.css"

const STATUS_LABEL: Record<string, string> = {
  pending: "Pending",
  running: "Running",
  succeeded: "Succeeded",
  failed: "Failed",
}

function StatTile({ label, value, variant }: {
  label: string
  value: number
  variant: "pipelines" | "runs" | "success" | "fail"
}) {
  return (
    <article className={`bc-stat bc-stat--${variant}`}>
      <span className="bc-stat__value">{value}</span>
      <span className="bc-stat__label">{label}</span>
    </article>
  )
}

function RunRow({ run }: { run: TaskRunSummary }) {
  const ts = run.created_at ? new Date(run.created_at) : null
  const time = ts
    ? ts.toLocaleString([], { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" })
    : "—"

  return (
    <tr className="bc-table__row">
      <td className="bc-table__cell bc-table__cell--id">
        <span className="bc-mono">#{run.id}</span>
      </td>
      <td className="bc-table__cell">{run.pipeline_name}</td>
      <td className="bc-table__cell">
        <span className={`bc-badge bc-badge--${run.status}`}>
          {STATUS_LABEL[run.status] ?? run.status}
        </span>
      </td>
      <td className="bc-table__cell bc-table__cell--time">{time}</td>
    </tr>
  )
}

export default function Dashboard() {
  const [stats, setStats] = useState<DashboardStats | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState("")

  const load = async () => {
    setLoading(true)
    setError("")
    const data = await fetchDashboardStats()
    if (data) {
      setStats(data)
    } else {
      setError("Failed to load dashboard data")
    }
    setLoading(false)
  }

  useEffect(() => {
    void load()
  }, [])

  if (loading) {
    return (
      <div className="bc-dash">
        <div className="bc-dash__skeleton">
          {Array.from({ length: 4 }).map((_, i) => (
            <div key={i} className="bc-stat bc-stat--skeleton" />
          ))}
        </div>
      </div>
    )
  }

  if (error) {
    return (
      <div className="bc-dash">
        <div className="bc-dash__error">
          <p>{error}</p>
          <button className="bc-btn" onClick={() => void load()}>Retry</button>
        </div>
      </div>
    )
  }

  const s = stats!

  return (
    <div className="bc-dash">
      <header className="bc-dash__head">
        <div>
          <h2 className="bc-dash__title">Dashboard</h2>
          <p className="bc-dash__subtitle">
            {s.pipelines_count} {s.pipelines_count === 1 ? "pipeline" : "pipelines"} ·
            {" "}{s.task_runs_count} {s.task_runs_count === 1 ? "run" : "runs"} total
          </p>
        </div>
        <button className="bc-btn" onClick={() => void load()} disabled={loading}>
          {loading ? "Loading..." : "Refresh"}
        </button>
      </header>

      {/* Stat tiles */}
      <div className="bc-dash__grid">
        <StatTile label="Pipelines" value={s.pipelines_count} variant="pipelines" />
        <StatTile label="Total Runs" value={s.task_runs_count} variant="runs" />
        <StatTile label="Succeeded" value={s.status_breakdown.succeeded} variant="success" />
        <StatTile label="Failed" value={s.status_breakdown.failed} variant="fail" />
      </div>

      {/* Status breakdown bar */}
      <div className="bc-dash__bar">
        {(["succeeded", "running", "pending", "failed"] as const).map((st) => {
          const count = s.status_breakdown[st]
          const total = s.task_runs_count || 1
          const pct = Math.round((count / total) * 100)
          return pct > 0 ? (
            <div
              key={st}
              className={`bc-dash__bar-seg bc-dash__bar-seg--${st}`}
              style={{ width: `${pct}%` }}
              title={`${STATUS_LABEL[st]}: ${count}`}
            />
          ) : null
        })}
      </div>

      {/* Recent runs table */}
      <section className="bc-dash__recent">
        <h3 className="bc-dash__section-title">Recent Runs</h3>
        {s.recent_runs.length === 0 ? (
          <p className="bc-dash__empty">No runs yet. Create a pipeline to get started.</p>
        ) : (
          <div className="bc-table-wrap">
            <table className="bc-table">
              <thead>
                <tr className="bc-table__row">
                  <th className="bc-table__head">ID</th>
                  <th className="bc-table__head">Pipeline</th>
                  <th className="bc-table__head">Status</th>
                  <th className="bc-table__head">Created</th>
                </tr>
              </thead>
              <tbody>
                {s.recent_runs.map((r) => (
                  <RunRow key={r.id} run={r} />
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </div>
  )
}
