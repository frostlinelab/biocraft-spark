import { useCallback, useEffect, useRef, useState } from "react"
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

const AUTO_SAVE_MS = 2000

type SaveState = "idle" | "saving" | "saved" | "error"

interface WorkflowCanvasProps {
  pipelineId: number
  onBack: () => void
  onRun?: () => void
}

export default function WorkflowCanvas({ pipelineId, onBack, onRun }: WorkflowCanvasProps) {
  const [nodes, setNodes, onNodesChange] = useNodesState([])
  const [edges, setEdges, onEdgesChange] = useEdgesState([])
  const [selectedNode, setSelectedNode] = useState<Node | null>(null)
  const [pipelineName, setPipelineName] = useState("")
  const [loading, setLoading] = useState(true)
  const [loadError, setLoadError] = useState("")
  const [saveState, setSaveState] = useState<SaveState>("idle")
  const [runState, setRunState] = useState<"idle" | "running" | "done" | "error">("idle")
  const [lastRunId, setLastRunId] = useState<number | null>(null)
  const saveTimer = useRef<ReturnType<typeof setTimeout> | null>(null)
  const isDirty = useRef(false)

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
          } else {
            setNodes(DEFAULT_NODES)
          }
          if (graph.edges && Array.isArray(graph.edges)) {
            setEdges(graph.edges)
          } else {
            setEdges(DEFAULT_EDGES)
          }
        } catch {
          setNodes(DEFAULT_NODES)
          setEdges(DEFAULT_EDGES)
        }
      } else {
        setNodes(DEFAULT_NODES)
        setEdges(DEFAULT_EDGES)
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
    isDirty.current = true
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

  const addNode = useCallback(() => {
    const id = `${Date.now()}`
    const newNode: Node = {
      id,
      type: "default",
      data: { label: `Node ${nodes.length + 1}` },
      position: {
        x: 100 + Math.random() * 400,
        y: 100 + Math.random() * 300,
      },
    }
    setNodes((nds: Node[]) => [...nds, newNode])
  }, [nodes.length, setNodes])

  const handleRun = useCallback(async () => {
    setRunState("running")
    const result = await runPipeline(pipelineId)
    if (result) {
      setRunState("done")
      setLastRunId(result.id)
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
          <button type="button" className="bc-canvas__btn" onClick={onBack}>
            ← Back
          </button>
          <span className="bc-canvas__stat" style={{ marginLeft: 12 }}>
            Loading...
          </span>
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
          <button type="button" className="bc-canvas__btn" onClick={onBack}>
            ← Back
          </button>
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
          <button type="button" className="bc-canvas__btn" onClick={addNode}>
            + Add Node
          </button>
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

      <div className="bc-canvas__flow">
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
      </div>

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
  )
}
