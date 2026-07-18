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
import { fetchPipeline, savePipeline, runPipeline, type PipelineDetail } from "../lib/api"

// ── Default initial graph ─────────────────────────────────────

const DEFAULT_NODES: Node[] = [
  {
    id: "1",
    type: "default",
    data: { label: "Start" },
    position: { x: 250, y: 40 },
  },
  {
    id: "2",
    type: "default",
    data: { label: "Process" },
    position: { x: 100, y: 160 },
  },
  {
    id: "3",
    type: "default",
    data: { label: "Process" },
    position: { x: 400, y: 160 },
  },
  {
    id: "4",
    type: "default",
    data: { label: "End" },
    position: { x: 250, y: 280 },
  },
]

const DEFAULT_EDGES: Edge[] = [
  { id: "e1-2", source: "1", target: "2", animated: true },
  { id: "e1-3", source: "1", target: "3", animated: true },
  { id: "e2-4", source: "2", target: "4", animated: true },
  { id: "e3-4", source: "3", target: "4", animated: true },
]

// ── Palette block definitions ─────────────────────────────────

interface BlockDef {
  id: string
  label: string
  sub: string
  icon: "start" | "process" | "io" | "condition"
  defaultLabel: string
}

const BLOCKS: BlockDef[] = [
  { id: "start", label: "Start / End", sub: "Entry & exit points", icon: "start", defaultLabel: "Start" },
  { id: "process", label: "Process", sub: "Compute step", icon: "process", defaultLabel: "Process" },
  { id: "input", label: "Input", sub: "File or data source", icon: "io", defaultLabel: "Input" },
  { id: "output", label: "Output", sub: "File or data sink", icon: "io", defaultLabel: "Output" },
  { id: "condition", label: "Condition", sub: "Branch / decision", icon: "condition", defaultLabel: "Condition" },
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
  const saveTimer = useRef<ReturnType<typeof setTimeout> | null>(null)
  const reactFlowWrapper = useRef<HTMLDivElement>(null)
  const nodeIdCounter = useRef(0)

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
            nodeIdCounter.current = 4
          }
          if (graph.edges && Array.isArray(graph.edges)) {
            setEdges(graph.edges)
          } else {
            setEdges(DEFAULT_EDGES)
          }
        } catch {
          setNodes(DEFAULT_NODES)
          setEdges(DEFAULT_EDGES)
          nodeIdCounter.current = 4
        }
      } else {
        setNodes(DEFAULT_NODES)
        setEdges(DEFAULT_EDGES)
        nodeIdCounter.current = 4
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

      const blockId = event.dataTransfer.getData("application/biocraft-block")
      if (!blockId || !reactFlowWrapper.current) return

      const blockDef = BLOCKS.find((b) => b.id === blockId)
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
        data: { label: blockDef.defaultLabel },
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
                <dt>Type</dt>
                <dd>{selectedNode.type ?? "default"}</dd>
                <dt>Position</dt>
                <dd className="bc-canvas__mono">
                  x={Math.round(selectedNode.position.x)}, y={Math.round(selectedNode.position.y)}
                </dd>
              </dl>
            </div>
          )}
        </div>

        {/* ── Right-side block palette ─────────────────────────── */}
        <aside className="bc-palette">
          <div className="bc-palette__head">Blocks</div>
          <div className="bc-palette__list">
            {BLOCKS.map((block) => (
              <div
                key={block.id}
                className="bc-palette__block"
                draggable
                onDragStart={(event) => {
                  event.dataTransfer.setData("application/biocraft-block", block.id)
                  event.dataTransfer.effectAllowed = "move"
                }}
              >
                <span className={`bc-palette__block-icon bc-palette__block-icon--${block.icon}`}>
                  <BlockIcon icon={block.icon} />
                </span>
                <span className="bc-palette__block-label">
                  {block.label}
                  <br />
                  <span className="bc-palette__block-sub">{block.sub}</span>
                </span>
              </div>
            ))}
          </div>
        </aside>
      </div>
    </div>
  )
}

// ── Block icon mini-svgs ───────────────────────────────────────

function BlockIcon({ icon }: { icon: "start" | "process" | "io" | "condition" }) {
  const size = 14
  switch (icon) {
    case "start":
      return (
        <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
          <circle cx="12" cy="12" r="9" />
        </svg>
      )
    case "process":
      return (
        <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
          <rect x="3" y="3" width="18" height="18" rx="3" />
        </svg>
      )
    case "io":
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
  }
}
