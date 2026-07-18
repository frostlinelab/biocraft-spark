import { memo } from "react"
import { Handle, Position, type NodeProps } from "@xyflow/react"

export interface PluginNodeData {
  label: string
  blockPlugin: string
  blockName: string
  blockIcon: string
  inputs: { name: string; label: string; portType: string; pattern: string; multiple: boolean }[]
  outputs: { name: string; label: string; portType: string; pattern: string; multiple: boolean }[]
  params: { name: string; label: string; paramType: string; default: unknown }[]
  hasRuntime: boolean
  /** Fan-out lanes — one per input file */
  lanes?: LaneDef[]
  /** Resource info badge */
  resourceBadge?: string
}

export interface LaneDef {
  fileName: string
  fileIndex: number
}

function PluginNode({ data }: NodeProps) {
  const nodeData = data as unknown as PluginNodeData
  const lanes = nodeData.lanes ?? []
  const hasLanes = lanes.length > 0

  return (
    <div className={`bc-node bc-node--plugin${hasLanes ? " bc-node--fanout" : ""}`}>
      <div className="bc-node__header">
        <span className={`bc-node__icon bc-node__icon--${nodeData.blockIcon}`}>
          <NodeIcon icon={nodeData.blockIcon} />
        </span>
        <span className="bc-node__label">{nodeData.label}</span>
        {nodeData.resourceBadge && (
          <span className="bc-node__resource">{nodeData.resourceBadge}</span>
        )}
      </div>

      {/* Fan-out lanes */}
      {hasLanes && (
        <div className="bc-node__lanes">
          <div className="bc-node__lanes-label">
            {lanes.length} {lanes.length === 1 ? "lane" : "lanes"}
          </div>
          <div className="bc-node__lanes-grid">
            {lanes.map((lane) => (
              <div key={lane.fileIndex} className="bc-node__lane">
                <span className="bc-node__lane-idx">{lane.fileIndex + 1}</span>
                <span className="bc-node__lane-name" title={lane.fileName}>
                  {lane.fileName}
                </span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Input handles — left side */}
      {nodeData.inputs.map((p, i) => (
        <Handle
          key={`in-${p.name}`}
          type="target"
          position={Position.Left}
          id={p.name}
          className={`bc-handle bc-handle--${p.portType}`}
          title={p.label}
          style={{ top: `${20 + i * 18}px` }}
        />
      ))}

      {/* Output handles — right side */}
      {nodeData.outputs.map((p, i) => (
        <Handle
          key={`out-${p.name}`}
          type="source"
          position={Position.Right}
          id={p.name}
          className={`bc-handle bc-handle--${p.portType}`}
          title={p.label}
          style={{ top: `${20 + i * 18}px` }}
        />
      ))}
    </div>
  )
}

function NodeIcon({ icon }: { icon: string }) {
  switch (icon) {
    case "beaker":
      return (
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
          <path d="M4 22h16" />
          <path d="M8 14h8" />
          <path d="M8 10h8" />
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
