// Biocraft-Spark — Workflow List page showing all pipelines

import { useCallback, useEffect, useState } from "react"
import {
  type PipelineSummary,
  fetchPipelines,
  createPipeline,
} from "../lib/api"
import "./WorkflowList.css"

export interface WorkflowListProps {
  onSelect: (pipelineId: number) => void
  onCreate: (pipelineId: number) => void
  refreshToken?: number
}

export default function WorkflowList({ onSelect, onCreate, refreshToken }: WorkflowListProps) {
  const [pipelines, setPipelines] = useState<PipelineSummary[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState("")
  const [creating, setCreating] = useState(false)
  const [newName, setNewName] = useState("")
  const [createError, setCreateError] = useState("")

  const load = useCallback(async () => {
    setLoading(true)
    setError("")
    const data = await fetchPipelines()
    if (data) {
      setPipelines(data)
    } else {
      setError("Failed to load workflows")
    }
    setLoading(false)
  }, [])

  useEffect(() => {
    void load()
  }, [load, refreshToken])

  const handleCreate = async () => {
    const name = newName.trim()
    if (!name) {
      setCreateError("Name is required")
      return
    }
    setCreateError("")
    const result = await createPipeline({ name })
    if (result) {
      onCreate(result.id)
    } else {
      setCreateError("Failed to create workflow")
    }
  }

  return (
    <div className="bc-wf-list">
      <header className="bc-wf-list__head">
        <div>
          <h2 className="bc-wf-list__title">Workflows</h2>
          <p className="bc-wf-list__subtitle">
            {pipelines.length} {pipelines.length === 1 ? "workflow" : "workflows"}
          </p>
        </div>
        <button
          className="bc-btn bc-btn--primary"
          onClick={() => {
            setCreating(true)
            setNewName("")
            setCreateError("")
          }}
        >
          + New Workflow
        </button>
      </header>

      {/* Create dialog */}
      {creating && (
        <div className="bc-create-bar">
          <div className="bc-create-bar__fields">
            <input
              className="bc-input"
              type="text"
              placeholder="Workflow name"
              value={newName}
              onChange={(e) => {
                setNewName(e.target.value)
                setCreateError("")
              }}
              onKeyDown={(e) => {
                if (e.key === "Enter") void handleCreate()
              }}
              autoFocus
            />
            {createError && (
              <span className="bc-create-bar__error">{createError}</span>
            )}
          </div>
          <div className="bc-create-bar__actions">
            <button className="bc-btn bc-btn--primary" onClick={() => void handleCreate()}>
              Create
            </button>
            <button className="bc-btn" onClick={() => setCreating(false)}>
              Cancel
            </button>
          </div>
        </div>
      )}

      {error ? (
        <div className="bc-wf-list__error">
          <p>{error}</p>
          <button className="bc-btn" onClick={() => void load()}>Retry</button>
        </div>
      ) : loading ? (
        <div className="bc-wf-list__loading">
          {Array.from({ length: 4 }).map((_, i) => (
            <div key={i} className="bc-wf-card bc-wf-card--skeleton" />
          ))}
        </div>
      ) : pipelines.length === 0 ? (
        <div className="bc-wf-list__empty">
          <p>No workflows yet.</p>
          <p className="bc-wf-list__empty-hint">
            Create your first workflow to get started.
          </p>
        </div>
      ) : (
        <div className="bc-wf-list__grid">
          {pipelines.map((p) => (
            <button
              key={p.id}
              type="button"
              className="bc-wf-card"
              onClick={() => onSelect(p.id)}
            >
              <div className="bc-wf-card__icon">
                <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round">
                  <circle cx="12" cy="5" r="2.5" />
                  <circle cx="5" cy="19" r="2.5" />
                  <circle cx="19" cy="19" r="2.5" />
                  <line x1="12" y1="7.5" x2="5" y2="16.5" />
                  <line x1="12" y1="7.5" x2="19" y2="16.5" />
                  <line x1="7.5" y1="19" x2="17.5" y2="19" />
                </svg>
              </div>
              <h3 className="bc-wf-card__name">{p.name}</h3>
              {p.description && (
                <p className="bc-wf-card__desc">{p.description}</p>
              )}
              <span className="bc-wf-card__time">
                Updated {new Date(p.updated_at).toLocaleDateString()}
              </span>
            </button>
          ))}
        </div>
      )}
    </div>
  )
}
