import { useCallback, useEffect, useRef, useState, type DragEvent } from "react"
import {
  ReactFlow,
  Background,
  Controls,
  MiniMap,
  addEdge,
  useNodesState,
  useEdgesState,
  type Connection,
  type Node,
  type Edge,
} from "@xyflow/react"
import "@xyflow/react/dist/style.css"
import "./WorkflowCanvas.css"
import {
  fetchPipeline,
  savePipeline,
  runPipeline,
  fetchBlocks,
  type PipelineDetail,
  type BlockDef,
  type BlockCategory,
} from "../lib/api"

// ── Default initial graph ─────────────────────────────────────

const DEFAULT_NODES: Node[] = [
  {
    id: "1",
    type: "default",
    data: { label: "Start", blockPlugin: "builtin", blockName: "start" },
    position: { x: 250, y: 50 },
  },
  {
    id: "2",
    type: "default",
    data: { label: "End", blockPlugin: "builtin", blockName: "end" },
    position: { x: 250, y: 250 },
  },
]

const DEFAULT_EDGES: Edge[] = [
  { id: "e1-2", source: "1", target: "2", animated: true },
]

// ── Constants ─────────────────────────────────────────────────

const AUTO_SAVE_MS = 2000

type SaveState = "idle" | "saving" | "saved" | "error"

interface WorkflowCanvasProps {
  pipelineId: number
  onBack: () => void
  onRun?: () => void
}

export default function WorkflowCanvas({ pipelineId, onBack, onRun }: WorkflowCanvasProps) {
  const [nodes, setNodes, onNodesChange] = useNodesState<Node>([])
  const [edges, setEdges, onEdgesChange] = useEdgesState<Edge>([])
  const [selectedNode, setSelectedNode] = useState<Node | null>(null)
  const [pipelineName, setPipelineName] = useState("")
  const [loading, setLoading] = useState(true)
  const [loadError, setLoadError] = useState("")
  const [saveState, setSaveState] = useState<SaveState>("idle")
  const [runState, setRunState] = useState<"idle" | "running" | "done" | "error">("idle")
  const [dragOver, setDragOver] = useState(false)
  const [categories, setCategories] = useState<BlockCategory[]>([])
  const [expandedGroups, setExpandedGroups] = useState<Set<string>>(new Set(["builtin"]))
  const saveTimer = useRef<ReturnType<typeof setTimeout> | null>(null)
  const reactFlowWrapper = useRef<HTMLDivElement>(null)
  const nodeIdCounter = useRef(0)

  // Load block categories on mount
  useEffect(() => {
    fetchBlocks().then(setCategories)
  }, [])

  // Reset node id counter when pipeline changes
  useEffect(() => {
    nodeIdCounter.current = 0
  }, [pipelineId])

  // Load pipeline data on mount or when pipelineId changes
  useEffect(() => {
    let cancelled = false
    setLoading(true)
    setLoadError("")
    fetchPipeline(pipelineId).then((p: PipelineDetail | null) => {
      if (cancelled) return
      if (!p) {
        setLoadError("Workflow not found")
        setLoading(false)
        return
      }
      setPipelineName(p.name)

      // Try to parse yaml_content as JSON for stored graph data
      if (p.yaml_content) {
        try {
          const graph = JSON.parse(p.yaml_content)
          if (graph.nodes && Array.isArray(graph.nodes)) {
            setNodes(graph.nodes)
            // Track max id
            const maxId = graph.nodes.reduce((max: number, n: Node) => {
              const num = parseInt(n.id, 10)
              return Number.isNaN(num) ? max : Math.max(max, num)
            }, 0)
            nodeIdCounter.current = maxId
          } else {
            setNodes(DEFAULT_NODES)
            nodeIdCounter.current = 2
          }
          if (graph.edges && Array.isArray(graph.edges)) {
            setEdges(graph.edges)
          } else {
            setEdges(DEFAULT_EDGES)
          }
        } catch {
          setNodes(DEFAULT_NODES)
          setEdges(DEFAULT_EDGES)
          nodeIdCounter.current = 2
        }
      } else {
        setNodes(DEFAULT_NODES)
        setEdges(DEFAULT_EDGES)
        nodeIdCounter.current = 2
      }
      setLoading(false)
    })
    return () => { cancelled = true }
  }, [pipelineId, setNodes, setEdges])

  // Debounced auto-save whenever nodes or edges change
  const doSave = useCallback(async () => {
    setSaveState("saving")
    const graph = JSON.stringify({ nodes, edges })
    const result = await savePipeline(pipelineId, { yaml_content: graph })
    if (result) {
      setSaveState("saved")
      setTimeout(() => setSaveState((s) => (s === "saved" ? "idle" : s)), 1500)
    } else {
      setSaveState("error")
    }
  }, [pipelineId, nodes, edges])

  useEffect(() => {
    if (loading) return // Don't save during initial load
    // Skip the first render which is from loading state -> loaded
    if (nodes.length === 0) return

    if (saveTimer.current) clearTimeout(saveTimer.current)
    setSaveState("idle")
    saveTimer.current = setTimeout(() => {
      void doSave()
    }, AUTO_SAVE_MS)

    return () => {
      if (saveTimer.current) clearTimeout(saveTimer.current)
    }
  }, [nodes, edges, loading, doSave])

  const onConnect = useCallback(
    (connection: Connection) => setEdges((eds: Edge[]) => addEdge(connection, eds)),
    [setEdges],
  )

  const onNodeClick = useCallback(
    (_event: React.MouseEvent, node: Node) => setSelectedNode(node),
    [],
  )

  const onPaneClick = useCallback(() => setSelectedNode(null), [])

  // ── Lookup helpers ──────────────────────────────────────────

  // Build a flat lookup map: "pluginName::blockName" → BlockDef
  const blockMap = useRef<Map<string, BlockDef>>(new Map())
  useEffect(() => {
    const map = new Map<string, BlockDef>()
    for (const cat of categories) {
      for (const b of cat.blocks) {
        map.set(`${b.pluginName}::${b.name}`, b)
      }
    }
    blockMap.current = map
  }, [categories])

  // ── Drag-and-drop from palette ──────────────────────────────

  const onDragOver = useCallback((event: DragEvent) => {
    event.preventDefault()
    event.dataTransfer.dropEffect = "move"
    setDragOver(true)
  }, [])

  const onDragLeave = useCallback(() => {
    setDragOver(false)
  }, [])

  const onDrop = useCallback(
    (event: DragEvent) => {
      event.preventDefault()
      setDragOver(false)

      // Data format: "pluginName::blockName"
      const blockKey = event.dataTransfer.getData("application/biocraft-block")
      if (!blockKey || !reactFlowWrapper.current) return

      const blockDef = blockMap.current.get(blockKey)
      if (!blockDef) return

      // Convert drop screen coords to flow coords
      const bounds = reactFlowWrapper.current.getBoundingClientRect()
      const position = {
        x: event.clientX - bounds.left - 60, // offset ~ half node width
        y: event.clientY - bounds.top - 20,
      }

      nodeIdCounter.current += 1
      const newNode: Node = {
        id: String(nodeIdCounter.current),
        type: "default",
        data: {
          label: blockDef.label,
          blockPlugin: blockDef.pluginName,
          blockName: blockDef.name,
          blockIcon: blockDef.icon,
          inputs: blockDef.inputs,
          outputs: blockDef.outputs,
          params: blockDef.params,
          hasRuntime: blockDef.hasRuntime,
        },
        position,
      }
      setNodes((nds: Node[]) => [...nds, newNode])
    },
    [setNodes],
  )

  const handleRun = useCallback(async () => {
    setRunState("running")
    const result = await runPipeline(pipelineId)
    if (result) {
      setRunState("done")
    } else {
      setRunState("error")
    }
    // Call the external onRun callback if provided
    if (onRun) onRun()
  }, [pipelineId, onRun])

  // ── Palette accordion toggle ────────────────────────────────

  const toggleGroup = useCallback((groupName: string) => {
    setExpandedGroups((prev) => {
      const next = new Set(prev)
      if (next.has(groupName)) {
        next.delete(groupName)
      } else {
        next.add(groupName)
      }
      return next
    })
  }, [])

  const nodeCount = nodes.length
  const edgeCount = edges.length

  if (loading) {
    return (
      <div className="bc-canvas">
        <div className="bc-canvas__toolbar">
          <div className="bc-canvas__toolbar-left">
            <button type="button" className="bc-canvas__btn" onClick={onBack}>
              ← Back
            </button>
            <span className="bc-canvas__stat" style={{ marginLeft: 12 }}>
              Loading...
            </span>
          </div>
        </div>
        <div className="bc-canvas__flow bc-canvas__flow--loading">
          <p className="bc-canvas__loading-text">Loading workflow...</p>
        </div>
      </div>
    )
  }

  if (loadError) {
    return (
      <div className="bc-canvas">
        <div className="bc-canvas__toolbar">
          <div className="bc-canvas__toolbar-left">
            <button type="button" className="bc-canvas__btn" onClick={onBack}>
              ← Back
            </button>
          </div>
        </div>
        <div className="bc-canvas__flow bc-canvas__flow--loading">
          <p className="bc-canvas__loading-text">{loadError}</p>
          <button className="bc-btn" onClick={onBack}>Go Back</button>
        </div>
      </div>
    )
  }

  return (
    <div className="bc-canvas">
      <div className="bc-canvas__toolbar">
        <div className="bc-canvas__toolbar-left">
          <button type="button" className="bc-canvas__btn" onClick={onBack}>
            ← Back
          </button>
          <span className="bc-canvas__pipeline-name">{pipelineName}</span>
        </div>
        <div className="bc-canvas__toolbar-right">
          {/* Save indicator */}
          <span className={`bc-save-indicator bc-save-indicator--${saveState}`}>
            {saveState === "saving" && "Saving..."}
            {saveState === "saved" && "✓ Saved"}
            {saveState === "error" && "⚠ Save failed"}
            {saveState === "idle" && ""}
          </span>
          <div className="bc-canvas__stats">
            <span className="bc-canvas__stat">
              <span className="bc-canvas__stat-value">{nodeCount}</span>
              <span className="bc-canvas__stat-label">{nodeCount === 1 ? "Node" : "Nodes"}</span>
            </span>
            <span className="bc-canvas__stat">
              <span className="bc-canvas__stat-value">{edgeCount}</span>
              <span className="bc-canvas__stat-label">{edgeCount === 1 ? "Edge" : "Edges"}</span>
            </span>
          </div>
          {onRun && (
            <button
              type="button"
              className={`bc-canvas__btn bc-canvas__btn--run${runState === "running" ? " bc-canvas__btn--running" : ""}`}
              onClick={() => void handleRun()}
              disabled={runState === "running"}
            >
              {runState === "running" ? "⟳ Running..." : runState === "done" ? "▶ Run Again" : "▶ Run"}
            </button>
          )}
        </div>
      </div>

      {/* Body: flow canvas + right palette */}
      <div className="bc-canvas__body">
        <div
          ref={reactFlowWrapper}
          className={`bc-canvas__flow${dragOver ? " bc-canvas__flow--drag-over" : ""}`}
          onDragOver={onDragOver}
          onDragLeave={onDragLeave}
          onDrop={onDrop}
        >
          <ReactFlow
            nodes={nodes}
            edges={edges}
            onNodesChange={onNodesChange}
            onEdgesChange={onEdgesChange}
            onConnect={onConnect}
            onNodeClick={onNodeClick}
            onPaneClick={onPaneClick}
            fitView
            attributionPosition="bottom-right"
          >
            <Background gap={20} size={1} />
            <Controls />
            <MiniMap
              nodeStrokeWidth={2}
              pannable
              zoomable
              style={{ background: "#1a1a1a" }}
              maskColor="rgba(0,0,0,0.6)"
            />
          </ReactFlow>

          {selectedNode && (
            <div className="bc-canvas__panel">
              <h3 className="bc-canvas__panel-title">Node Inspector</h3>
              <dl className="bc-canvas__panel-dl">
                <dt>ID</dt>
                <dd className="bc-canvas__mono">{selectedNode.id}</dd>
                <dt>Label</dt>
                <dd>{String(selectedNode.data.label ?? "—")}</dd>
                <dt>Plugin</dt>
                <dd>{String(selectedNode.data.blockPlugin ?? "—")}</dd>
                <dt>Block</dt>
                <dd>{String(selectedNode.data.blockName ?? "—")}</dd>
                <dt>Type</dt>
                <dd>{selectedNode.type ?? "default"}</dd>
                <dt>Position</dt>
                <dd className="bc-canvas__mono">
                  x={Math.round(selectedNode.position.x)}, y={Math.round(selectedNode.position.y)}
                </dd>
              </dl>
              {/* Show ports if available */}
              {selectedNode.data.inputs && (selectedNode.data.inputs as BlockDef["inputs"]).length > 0 && (
                <>
                  <h4 className="bc-canvas__panel-subtitle">Input Ports</h4>
                  <ul className="bc-canvas__panel-ports">
                    {(selectedNode.data.inputs as BlockDef["inputs"]).map((p) => (
                      <li key={p.name}>
                        <span className="bc-canvas__port-type">{p.portType}</span> {p.label}
                        {p.pattern && <span className="bc-canvas__port-pattern">{p.pattern}</span>}
                      </li>
                    ))}
                  </ul>
                </>
              )}
              {selectedNode.data.outputs && (selectedNode.data.outputs as BlockDef["outputs"]).length > 0 && (
                <>
                  <h4 className="bc-canvas__panel-subtitle">Output Ports</h4>
                  <ul className="bc-canvas__panel-ports">
                    {(selectedNode.data.outputs as BlockDef["outputs"]).map((p) => (
                      <li key={p.name}>
                        <span className="bc-canvas__port-type">{p.portType}</span> {p.label}
                        {p.pattern && <span className="bc-canvas__port-pattern">{p.pattern}</span>}
                      </li>
                    ))}
                  </ul>
                </>
              )}
            </div>
          )}
        </div>

        {/* ── Right-side categorized block palette ─────────────── */}
        <aside className="bc-palette">
          <div className="bc-palette__head">Blocks</div>
          <div className="bc-palette__list">
            {categories.map((cat) => {
              const isExpanded = expandedGroups.has(cat.name)
              return (
                <div key={cat.name} className="bc-palette__group">
                  <button
                    type="button"
                    className={`bc-palette__group-header${isExpanded ? " bc-palette__group-header--open" : ""}`}
                    onClick={() => toggleGroup(cat.name)}
                  >
                    <span className="bc-palette__group-chevron">{isExpanded ? "▾" : "▸"}</span>
                    <span className="bc-palette__group-icon">
                      <BlockIcon icon={cat.icon} />
                    </span>
                    <span className="bc-palette__group-label">{cat.label}</span>
                    <span className="bc-palette__group-count">{cat.blocks.length}</span>
                  </button>
                  {isExpanded && (
                    <div className="bc-palette__group-blocks">
                      {cat.blocks.map((block) => (
                        <div
                          key={`${block.pluginName}::${block.name}`}
                          className="bc-palette__block"
                          draggable
                          onDragStart={(event) => {
                            event.dataTransfer.setData(
                              "application/biocraft-block",
                              `${block.pluginName}::${block.name}`,
                            )
                            event.dataTransfer.effectAllowed = "move"
                          }}
                          title={block.description}
                        >
                          <span className={`bc-palette__block-icon bc-palette__block-icon--${block.icon}`}>
                            <BlockIcon icon={block.icon} />
                          </span>
                          <span className="bc-palette__block-label">
                            {block.label}
                            <br />
                            <span className="bc-palette__block-sub">{block.description.slice(0, 40)}{block.description.length > 40 ? "…" : ""}</span>
                          </span>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              )
            })}
          </div>
        </aside>
      </div>
    </div>
  )
}

// ── Block icon mini-svgs ───────────────────────────────────────

type IconKey = string

function BlockIcon({ icon }: { icon: IconKey }) {
  const size = 14
  switch (icon) {
    case "start":
      return (
        <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
          <circle cx="12" cy="12" r="9" />
        </svg>
      )
    case "end":
      return (
        <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
          <circle cx="12" cy="12" r="9" />
          <line x1="12" y1="5" x2="12" y2="19" />
        </svg>
      )
    case "process":
      return (
        <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
          <rect x="3" y="3" width="18" height="18" rx="3" />
        </svg>
      )
    case "io":
    case "input":
    case "output":
      return (
        <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
          <polygon points="12,2 22,8.5 22,15.5 12,22 2,15.5 2,8.5" />
        </svg>
      )
    case "condition":
      return (
        <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
          <path d="M12 2l10 10-10 10L2 12z" />
        </svg>
      )
    // Plugin category / block icons
    case "microscope":
      return (
        <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
          <circle cx="12" cy="6" r="4" />
          <line x1="12" y1="10" x2="12" y2="18" />
          <line x1="8" y1="14" x2="16" y2="14" />
          <line x1="10" y1="18" x2="14" y2="18" />
        </svg>
      )
    case "beaker":
      return (
        <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
          <path d="M4 22h16" />
          <path d="M8 14h8" />
          <path d="M8 10h8" />
          <path d="M9 2v10.2a6 6 0 1 0 6 0V2" />
        </svg>
      )
    case "dna":
      return (
        <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
          <path d="M4 21c2.5-2.5 5-4 12-4s9.5 1.5 4 0-5-4-12-4-9.5-1.5-4 0" />
          <path d="M4 3c2.5 2.5 5 4 12 4s9.5-1.5 4 0-5 4-12 4-9.5 1.5-4 0" />
        </svg>
      )
    case "filter":
      return (
        <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
          <polygon points="22 3 2 3 10 12.46 10 19 14 21 14 12.46 22 3" />
        </svg>
      )
    case "wrench":
      return (
        <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
          <path d="M14.7 6.3a1 1 0 0 0 0 1.4l1.6 1.6a1 1 0 0 0 1.4 0l3.77-3.77a6 6 0 0 1-7.94 7.94l-6.91 6.91a2.12 2.12 0 0 1-3-3l6.91-6.91a6 6 0 0 1 7.94-7.94l-3.76 3.76z" />
        </svg>
      )
    case "builtin":
      return (
        <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
          <path d="M12 2L2 7l10 5 10-5-10-5z" />
          <path d="M2 17l10 5 10-5" />
          <path d="M2 12l10 5 10-5" />
        </svg>
      )
    default:
      return (
        <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
          <rect x="3" y="3" width="18" height="18" rx="3" />
        </svg>
      )
  }
}
