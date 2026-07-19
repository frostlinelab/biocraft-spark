import { memo, useCallback, useRef, useState, type DragEvent, type ChangeEvent } from "react"
import { Handle, Position, type NodeProps } from "@xyflow/react"
import { uploadFiles, type UploadedFile } from "../../lib/api"

export interface InputNodeData {
  label: string
  blockPlugin: string
  blockName: string
  blockIcon: string
  files?: UploadedFile[]
  params?: Record<string, unknown>
  /** Called by InputNode when files are added or removed, so the canvas can persist the change */
  onUpdateFiles?: (nodeId: string, files: UploadedFile[]) => void
}

function InputNode({ id, data }: NodeProps) {
  const nodeData = data as unknown as InputNodeData
  const files = nodeData.files ?? []
  const fileCount = files.length
  const fileInputRef = useRef<HTMLInputElement>(null)
  const [dragover, setDragover] = useState(false)
  const [uploading, setUploading] = useState(false)
  const [error, setError] = useState("")

  // ── Click-to-browse ──────────────────────────────────────────
  const handleBrowse = useCallback(() => {
    fileInputRef.current?.click()
  }, [])

  const processFiles = useCallback(
    async (fileList: FileList | null) => {
      if (!fileList || fileList.length === 0) return
      setUploading(true)
      setError("")
      try {
        const uploaded = await uploadFiles(Array.from(fileList))
        if (uploaded.length === 0) {
          setError("Upload failed")
          return
        }
        // Merge with existing, deduplicate by name+size
        const existing = nodeData.files ?? []
        const seen = new Set(existing.map((f) => `${f.name}|${f.size}`))
        const fresh = uploaded.filter((u) => !seen.has(`${u.name}|${u.size}`))
        const merged = [...existing, ...fresh]
        nodeData.onUpdateFiles?.(id, merged)
      } catch {
        setError("Upload error")
      } finally {
        setUploading(false)
      }
    },
    [id, nodeData.files, nodeData.onUpdateFiles],
  )

  const handleFileChange = useCallback(
    (e: ChangeEvent<HTMLInputElement>) => {
      void processFiles(e.target.files)
      // Reset so the same file can be re-selected
      if (fileInputRef.current) fileInputRef.current.value = ""
    },
    [processFiles],
  )

  // ── Drag-and-drop real files ─────────────────────────────────
  const onDragOver = useCallback((e: DragEvent) => {
    e.preventDefault()
    e.stopPropagation()
    e.dataTransfer.dropEffect = "copy"
    setDragover(true)
  }, [])

  const onDragLeave = useCallback((e: DragEvent) => {
    e.preventDefault()
    e.stopPropagation()
    setDragover(false)
  }, [])

  const onDrop = useCallback(
    (e: DragEvent) => {
      e.preventDefault()
      e.stopPropagation()
      setDragover(false)
      void processFiles(e.dataTransfer.files)
    },
    [processFiles],
  )

  // ── Remove a single file ─────────────────────────────────────
  const removeFile = useCallback(
    (index: number) => {
      const next = files.filter((_, i) => i !== index)
      nodeData.onUpdateFiles?.(id, next)
    },
    [id, files, nodeData.onUpdateFiles],
  )

  return (
    <div className="bc-node bc-node--input">
      {/* Hidden file input for click-to-browse */}
      <input
        ref={fileInputRef}
        type="file"
        multiple
        className="bc-node__file-input-hidden"
        onChange={handleFileChange}
        // Accept anything; file validation belongs to downstream blocks
      />

      <div className="bc-node__header">
        <span className="bc-node__icon bc-node__icon--input">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
            <polygon points="12,2 22,8.5 22,15.5 12,22 2,15.5 2,8.5" />
          </svg>
        </span>
        <span className="bc-node__label">{nodeData.label}</span>
        {fileCount > 0 && (
          <span className="bc-node__badge">{fileCount} {fileCount === 1 ? "file" : "files"}</span>
        )}
      </div>

      {/* File list / drop zone */}
      <div
        className={`bc-node__body${dragover ? " bc-node__body--dragover" : ""}`}
        onDragOver={onDragOver}
        onDragLeave={onDragLeave}
        onDrop={onDrop}
      >
        {uploading ? (
          <div className="bc-node__uploading">
            <span className="bc-node__spinner" />
            <span>Uploading...</span>
          </div>
        ) : fileCount === 0 ? (
          <button
            type="button"
            className="bc-node__dropzone"
            onClick={handleBrowse}
          >
            <p className="bc-node__dropzone-text">
              Drop files here
              <br />
              <span className="bc-node__dropzone-hint">or click to browse</span>
            </p>
          </button>
        ) : (
          <>
            <ul className="bc-node__filelist">
              {files.map((f, i) => (
                <li key={f.id ?? `${f.name}-${i}`} className="bc-node__fileitem">
                  <span className="bc-node__filename" title={f.name}>
                    {f.name}
                  </span>
                  <span className="bc-node__filesize">
                    {formatSize(f.size)}
                  </span>
                  <button
                    type="button"
                    className="bc-node__file-remove"
                    onClick={(e) => {
                      e.stopPropagation()
                      removeFile(i)
                    }}
                    title="Remove file"
                  >
                    ×
                  </button>
                </li>
              ))}
            </ul>
            <button
              type="button"
              className="bc-node__add-more"
              onClick={handleBrowse}
            >
              + Add files
            </button>
          </>
        )}
        {error && <p className="bc-node__upload-error">{error}</p>}
      </div>

      {/* Output handle — files go downward to next node */}
      <Handle
        type="source"
        position={Position.Bottom}
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
