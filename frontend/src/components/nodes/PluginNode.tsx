import { memo } from "react"
import { Handle, Position, type NodeProps } from "@xyflow/react"

// ── Data types ────────────────────────────────────────────────────────────────

export interface PluginNodeParam {
  name: string
  label: string
  paramType: "string" | "integer" | "float" | "boolean" | "select"
  default: unknown
  min?: number | null
  max?: number | null
  options?: string[]
}

export interface PluginNodePort {
  name: string
  label: string
  portType: string
  pattern: string
  multiple: boolean
}

/** One file entry inside a fan-out wave. */
export interface LaneDef {
  fileName: string
  fileIndex: number
}

export interface PluginNodeData {
  label: string
  blockPlugin: string
  blockName: string
  blockIcon: string
  inputs: PluginNodePort[]
  outputs: PluginNodePort[]
  params: PluginNodeParam[]
  hasRuntime: boolean
  /** Current param values — keyed by param name. Saved in node.data. */
  paramValues?: Record<string, string | number | boolean>
  /**
   * Fan-out waves: outer array = waves (sequential), inner array = lanes
   * (parallel instances within that wave). Populated by WorkflowCanvas when
   * files are attached to an Input node feeding this block.
   */
  waves?: LaneDef[][]
  /** Callback injected by WorkflowCanvas to propagate param edits. */
  onUpdateParams?: (
    nodeId: string,
    paramValues: Record<string, string | number | boolean>,
  ) => void
}

// ── Component ─────────────────────────────────────────────────────────────────

function PluginNode({ id, data }: NodeProps) {
  const d = data as unknown as PluginNodeData

  // Split inputs by direction: files go LEFT, flow (signal/string/number) go TOP
  const fileInputs = d.inputs.filter(
    (p) => p.portType === "file" || p.portType === "directory",
  )
  const flowInputs = d.inputs.filter(
    (p) => p.portType !== "file" && p.portType !== "directory",
  )

  const paramValues = (d.paramValues ?? {}) as Record<string, string | number | boolean>
  const waves = d.waves ?? []
  const hasFanout = waves.length > 0

  // Derive threads display from params (look for a param named "threads" or first integer)
  const threadParam =
    d.params.find((p) => p.name === "threads") ??
    d.params.find((p) => p.paramType === "integer")
  const threadCount =
    threadParam != null
      ? Number(paramValues[threadParam.name] ?? threadParam.default ?? 1)
      : null

  function setParam(name: string, value: string | number | boolean) {
    d.onUpdateParams?.(id, { ...paramValues, [name]: value })
  }

  return (
    <div className={`bc-node bc-node--plugin${hasFanout ? " bc-node--fanout" : ""}`}>

      {/* ── Header ──────────────────────────────────────────────── */}
      <div className="bc-node__header">
        <span className={`bc-node__icon bc-node__icon--${d.blockIcon}`}>
          <NodeIcon icon={d.blockIcon} />
        </span>
        <span className="bc-node__label">{d.label}</span>
      </div>

      {/* ── Body row: params left, resource panel right ──────────── */}
      <div className="bc-node__body-row">

        {/* Params section (left) */}
        {d.params.length > 0 && (
          <div className="bc-node__params">
            <div className="bc-node__params-head">Params</div>
            {d.params.map((p) => {
              const raw = paramValues[p.name]
              const value = raw !== undefined ? raw : p.default
              return (
                <div key={p.name} className="bc-node__param-row">
                  <label className="bc-node__param-label" title={p.label}>
                    {p.label}
                  </label>
                  {p.paramType === "boolean" ? (
                    <input
                      type="checkbox"
                      className="bc-node__param-check"
                      checked={Boolean(value)}
                      onChange={(e) => setParam(p.name, e.target.checked)}
                    />
                  ) : p.paramType === "select" && p.options?.length ? (
                    <select
                      className="bc-node__param-select"
                      value={String(value ?? "")}
                      onChange={(e) => setParam(p.name, e.target.value)}
                    >
                      {p.options.map((o) => (
                        <option key={o} value={o}>{o}</option>
                      ))}
                    </select>
                  ) : (
                    <input
                      type={
                        p.paramType === "integer" || p.paramType === "float"
                          ? "number"
                          : "text"
                      }
                      className={`bc-node__param-input${
                        p.paramType === "integer" || p.paramType === "float"
                          ? " bc-node__param-input--number"
                          : ""
                      }`}
                      value={String(value ?? "")}
                      min={p.min ?? undefined}
                      max={p.max ?? undefined}
                      step={
                        p.paramType === "float"
                          ? "any"
                          : p.paramType === "integer"
                            ? "1"
                            : undefined
                      }
                      onChange={(e) => {
                        const v = e.target.value
                        setParam(
                          p.name,
                          p.paramType === "integer"
                            ? parseInt(v, 10) || 0
                            : p.paramType === "float"
                              ? parseFloat(v) || 0
                              : v,
                        )
                      }}
                    />
                  )}
                </div>
              )
            })}
          </div>
        )}

        {/* Resource panel (right): thread count + fan-out waves */}
        <div className="bc-node__res-panel">
          {threadCount !== null && (
            <div className="bc-node__res-row">
              <span className="bc-node__res-icon">⚙</span>
              <span className="bc-node__res-value">{threadCount}t</span>
            </div>
          )}
          {hasFanout ? (
            <div className="bc-node__waves">
              {waves.map((wave, wi) => (
                <div key={wi} className="bc-node__wave">
                  <span className="bc-node__wave-label">W{wi + 1}</span>
                  <span className="bc-node__wave-dots">
                    {wave.map((lane) => (
                      <span
                        key={lane.fileIndex}
                        className="bc-node__wave-dot"
                        title={lane.fileName}
                      />
                    ))}
                  </span>
                </div>
              ))}
            </div>
          ) : (
            <div className="bc-node__res-row bc-node__res-row--idle">
              <span className="bc-node__res-icon">▸</span>
              <span className="bc-node__res-value">ready</span>
            </div>
          )}
        </div>
      </div>

      {/* ── Port summary footer ──────────────────────────────────── */}
      {(fileInputs.length > 0 || flowInputs.length > 0 || d.outputs.length > 0) && (
        <div className="bc-node__ports-foot">
          {fileInputs.length > 0 && (
            <span className="bc-node__ports-tag bc-node__ports-tag--left">
              ← {fileInputs.length} data
            </span>
          )}
          {flowInputs.length > 0 && (
            <span className="bc-node__ports-tag bc-node__ports-tag--top">
              ↑ {flowInputs.length} flow
            </span>
          )}
          {d.outputs.length > 0 && (
            <span className="bc-node__ports-tag bc-node__ports-tag--bottom">
              ↓ {d.outputs.length} out
            </span>
          )}
        </div>
      )}

      {/* ── Handles ─────────────────────────────────────────────── */}

      {/* TOP: flow-control inputs (signal, string, number) */}
      {flowInputs.map((p, i) => (
        <Handle
          key={`in-${p.name}`}
          type="target"
          position={Position.Top}
          id={p.name}
          className={`bc-handle bc-handle--${p.portType}`}
          title={`${p.label} (flow)`}
          style={{ left: `${40 + i * 24}px` }}
        />
      ))}

      {/* LEFT: file / directory inputs */}
      {fileInputs.map((p, i) => (
        <Handle
          key={`in-file-${p.name}`}
          type="target"
          position={Position.Left}
          id={p.name}
          className={`bc-handle bc-handle--${p.portType}`}
          title={`${p.label} (data)`}
          style={{ top: `${36 + i * 22}px` }}
        />
      ))}

      {/* BOTTOM: all outputs */}
      {d.outputs.map((p, i) => (
        <Handle
          key={`out-${p.name}`}
          type="source"
          position={Position.Bottom}
          id={p.name}
          className={`bc-handle bc-handle--${p.portType}`}
          title={p.label}
          style={{ left: `${40 + i * 24}px` }}
        />
      ))}
    </div>
  )
}

// ── Icon ──────────────────────────────────────────────────────────────────────

function NodeIcon({ icon }: { icon: string }) {
  switch (icon) {
    case "beaker":
      return (
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
          <path d="M4 22h16" /><path d="M8 14h8" /><path d="M8 10h8" />
          <path d="M9 2v10.2a6 6 0 1 0 6 0V2" />
        </svg>
      )
    case "microscope":
      return (
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
          <circle cx="12" cy="6" r="4" />
          <line x1="12" y1="10" x2="12" y2="18" />
          <line x1="8" y1="14" x2="16" y2="14" />
          <line x1="10" y1="18" x2="14" y2="18" />
        </svg>
      )
    case "filter":
      return (
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
          <polygon points="22 3 2 3 10 12.46 10 19 14 21 14 12.46 22 3" />
        </svg>
      )
    case "dna":
      return (
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
          <path d="M4 21c2.5-2.5 5-4 12-4s9.5 1.5 4 0-5-4-12-4-9.5-1.5-4 0" />
          <path d="M4 3c2.5 2.5 5 4 12 4s9.5-1.5 4 0-5 4-12 4-9.5 1.5-4 0" />
        </svg>
      )
    default:
      return (
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
          <rect x="3" y="3" width="18" height="18" rx="3" />
        </svg>
      )
  }
}

export default memo(PluginNode)
