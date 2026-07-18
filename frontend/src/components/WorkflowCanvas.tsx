import { useCallback, useState } from "react"
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

const initialNodes: Node[] = [
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

const initialEdges: Edge[] = [
  { id: "e1-2", source: "1", target: "2", animated: true },
  { id: "e1-3", source: "1", target: "3", animated: true },
  { id: "e2-4", source: "2", target: "4", animated: true },
  { id: "e3-4", source: "3", target: "4", animated: true },
]

export default function WorkflowCanvas() {
  const [nodes, setNodes, onNodesChange] = useNodesState(initialNodes)
  const [edges, setEdges, onEdgesChange] = useEdgesState(initialEdges)
  const [selectedNode, setSelectedNode] = useState<Node | null>(null)

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

  const nodeCount = nodes.length
  const edgeCount = edges.length

  return (
    <div className="bc-canvas">
      <div className="bc-canvas__toolbar">
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
