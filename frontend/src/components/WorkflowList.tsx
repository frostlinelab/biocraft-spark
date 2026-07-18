// Biocraft-Spark — Workflow List page showing all pipelines
// Supports multi-select management and modal creation

import { useCallback, useEffect, useState } from "react"
import {
  type PipelineSummary,
  fetchPipelines,
  createPipeline,
  deletePipelines,
} from "../lib/api"
import "./WorkflowList.css"

export interface WorkflowListProps {
  onSelect: (pipelineId: string) => void
  onCreate: (pipelineId: string) => void
  refreshToken?: number
}

export default function WorkflowList({ onSelect, onCreate, refreshToken }: WorkflowListProps) {
  const [pipelines, setPipelines] = useState<PipelineSummary[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState("")
  const [showModal, setShowModal] = useState(false)
  const [newName, setNewName] = useState("")
  const [newDesc, setNewDesc] = useState("")
  const [createError, setCreateError] = useState("")
  const [creating, setCreating] = useState(false)
  // Multi-select state
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set())

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

  const openModal = () => {
    setNewName("")
    setNewDesc("")
    setCreateError("")
    setShowModal(true)
  }

  const handleCreate = async () => {
    const name = newName.trim()
    if (!name) {
      setCreateError("Name is required")
      return
    }
    setCreateError("")
    setCreating(true)
    const result = await createPipeline({
      name,
      description: newDesc.trim() || undefined,
    })
    if (result) {
      setShowModal(false)
      onCreate(result.id)
    } else {
      setCreateError("Failed to create workflow")
    }
    setCreating(false)
  }

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter") {
      e.preventDefault()
      void handleCreate()
    }
    if (e.key === "Escape") {
      setShowModal(false)
    }
  }

  // ── Multi-select helpers ────────────────────────────────────

  const toggleSelect = (id: string) => {
    setSelectedIds((prev) => {
      const next = new Set(prev)
      if (next.has(id)) {
        next.delete(id)
      } else {
        next.add(id)
      }
      return next
    })
  }

  const selectAll = () => {
    setSelectedIds(new Set(pipelines.map((p) => p.id)))
  }

  const deselectAll = () => {
    setSelectedIds(new Set())
  }

  const handleDeleteSelected = async () => {
    if (selectedIds.size === 0) return
    const ok = await deletePipelines([...selectedIds])
    if (ok) {
      setSelectedIds(new Set())
      void load()
    }
  }

  const batchCount = selectedIds.size
  const allSelected = pipelines.length > 0 && batchCount === pipelines.length

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
          onClick={openModal}
        >
          + New Workflow
        </button>
      </header>

      {/* ── Batch action toolbar ─────────────────────────────── */}
      {batchCount > 0 && (
        <div className="bc-wf-batch">
          <span className="bc-wf-batch__count">
            {batchCount} {batchCount === 1 ? "workflow" : "workflows"} selected
          </span>
          <div className="bc-wf-batch__actions">
            <button
              className="bc-btn"
              onClick={allSelected ? deselectAll : selectAll}
            >
              {allSelected ? "Deselect All" : "Select All"}
            </button>
            <button
              className="bc-btn bc-btn--danger"
              onClick={() => void handleDeleteSelected()}
            >
              Delete Selected
            </button>
          </div>
        </div>
      )}

      {/* ── List ─────────────────────────────────────────────── */}
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
          {pipelines.map((p) => {
            const isSelected = selectedIds.has(p.id)
            return (
              <button
                key={p.id}
                type="button"
                className={`bc-wf-card${isSelected ? " bc-wf-card--selected" : ""}`}
                onClick={() => onSelect(p.id)}
              >
                <input
                  type="checkbox"
                  className="bc-wf-card__check"
                  checked={isSelected}
                  onChange={() => toggleSelect(p.id)}
                  onClick={(e) => e.stopPropagation()}
                  title="Select workflow"
                />
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
            )
          })}
        </div>
      )}

      {/* ── Create Modal ─────────────────────────────────────── */}
      {showModal && (
        <div
          className="bc-modal-overlay"
          onClick={() => setShowModal(false)}
          onKeyDown={handleKeyDown}
        >
          <div className="bc-modal" onClick={(e) => e.stopPropagation()}>
            <h3 className="bc-modal__title">New Workflow</h3>
            <p className="bc-modal__subtitle">
              Create a new analysis pipeline to get started.
            </p>

            <div className="bc-modal__field">
              <label className="bc-modal__label" htmlFor="wf-name">Name</label>
              <input
                id="wf-name"
                className="bc-input bc-input--block"
                type="text"
                placeholder="e.g. RNA-seq Pipeline"
                value={newName}
                onChange={(e) => {
                  setNewName(e.target.value)
                  setCreateError("")
                }}
                onKeyDown={handleKeyDown}
                autoFocus
              />
            </div>

            <div className="bc-modal__field">
              <label className="bc-modal__label" htmlFor="wf-desc">Description (optional)</label>
              <textarea
                id="wf-desc"
                className="bc-textarea"
                placeholder="Brief description of what this workflow does..."
                value={newDesc}
                onChange={(e) => setNewDesc(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter" && !e.shiftKey) {
                    e.preventDefault()
                    void handleCreate()
                  }
                  if (e.key === "Escape") setShowModal(false)
                }}
                rows={3}
              />
            </div>

            {createError && (
              <p className="bc-modal__error">{createError}</p>
            )}

            <div className="bc-modal__actions">
              <button
                className="bc-btn"
                onClick={() => setShowModal(false)}
              >
                Cancel
              </button>
              <button
                className="bc-btn bc-btn--primary"
                onClick={() => void handleCreate()}
                disabled={creating}
              >
                {creating ? "Creating..." : "Create Workflow"}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
