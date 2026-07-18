import { memo } from "react"
import { Handle, Position, type NodeProps } from "@xyflow/react"

export interface InputNodeData {
  label: string
  blockPlugin: string
  blockName: string
  blockIcon: string
  files?: InputFileEntry[]
  params?: Record<string, unknown>
}

export interface InputFileEntry {
  name: string
  size: number
  type: string
}

function InputNode({ data }: NodeProps) {
  const nodeData = data as unknown as InputNodeData
  const files = nodeData.files ?? []
  const fileCount = files.length

  return (
    <div className="bc-node bc-node--input">
      <div className="bc-node__header">
        <span className="bc-node__icon bc-node__icon--input">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
            <polygon points="12,2 22,8.5 22,15.5 12,22 2,15.5 2,8.5" />
          </svg>
        </span>
        <span className="bc-node__label">{nodeData.label}</span>
        {fileCount > 0 && (
          <span className="bc-node__badge">{fileCount} files</span>
        )}
      </div>

      {/* File list / drop zone */}
      <div className="bc-node__body">
        {fileCount === 0 ? (
          <div className="bc-node__dropzone">
            <p className="bc-node__dropzone-text">
              Drop files here
              <br />
              <span className="bc-node__dropzone-hint">or use the file picker</span>
            </p>
          </div>
        ) : (
          <ul className="bc-node__filelist">
            {files.map((f, i) => (
              <li key={i} className="bc-node__fileitem">
                <span className="bc-node__filename" title={f.name}>
                  {f.name}
                </span>
                <span className="bc-node__filesize">
                  {formatSize(f.size)}
                </span>
              </li>
            ))}
          </ul>
        )}
      </div>

      {/* Output handle — files fan out from here */}
      <Handle
        type="source"
        position={Position.Right}
        id="files"
        className="bc-handle bc-handle--file"
      />
    </div>
  )
}

function formatSize(bytes: number): string {
  if (bytes === 0) return "0 B"
  const units = ["B", "KB", "MB", "GB"]
  const i = Math.min(Math.floor(Math.log(bytes) / Math.log(1024)), units.length - 1)
  return `${(bytes / Math.pow(1024, i)).toFixed(i === 0 ? 0 : 1)} ${units[i]}`
}

export default memo(InputNode)
