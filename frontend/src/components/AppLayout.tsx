import { useState, useCallback } from "react"
import Sidebar, { type NavView } from "./Sidebar"
import Dashboard from "./Dashboard"
import WorkflowCanvas from "./WorkflowCanvas"
import WorkflowList from "./WorkflowList"
import TaskList from "./TaskList"
import RuntimeHealthPanel from "./RuntimeHealthPanel"
import "./AppLayout.css"
import "./WorkflowList.css"

export default function AppLayout() {
  const [view, setView] = useState<NavView>("dashboard")
  // Workflow state
  const [editingPipelineId, setEditingPipelineId] = useState<string | null>(null)
  const [workflowRefreshToken, setWorkflowRefreshToken] = useState(0)

  const handleSelectWorkflow = useCallback((pipelineId: string) => {
    setEditingPipelineId(pipelineId)
  }, [])

  const handleCreateWorkflow = useCallback((pipelineId: string) => {
    setWorkflowRefreshToken((t) => t + 1)
    setEditingPipelineId(pipelineId)
  }, [])

  const handleBackToList = useCallback(() => {
    setEditingPipelineId(null)
    setWorkflowRefreshToken((t) => t + 1)
  }, [])

  const handleRunWorkflow = useCallback(() => {
    // Will be wired up in the next feature
    setView("tasks")
  }, [setView])

  return (
    <div className="bc-layout">
      <Sidebar active={view} onChange={setView} />
      <main className="bc-layout__main">
        {view === "dashboard" && <Dashboard />}
        {view === "workflows" && (
          editingPipelineId != null ? (
            <WorkflowCanvas
              pipelineId={editingPipelineId}
              onBack={handleBackToList}
              onRun={handleRunWorkflow}
            />
          ) : (
            <WorkflowList
              onSelect={handleSelectWorkflow}
              onCreate={handleCreateWorkflow}
              refreshToken={workflowRefreshToken}
            />
          )
        )}
        {view === "tasks" && <TaskList />}
        {view === "health" && (
          <div className="bc-layout__health">
            <RuntimeHealthPanel pollMs={15000} />
          </div>
        )}
        {view === "n8n" && (
          <div className="bc-layout__placeholder">
            <div className="bc-placeholder">
              <div className="bc-placeholder__icon">
                <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round" strokeLinejoin="round">
                  <rect x="3" y="3" width="7" height="7" rx="1.5" />
                  <rect x="14" y="3" width="7" height="7" rx="1.5" />
                  <rect x="3" y="14" width="7" height="7" rx="1.5" />
                  <rect x="14" y="14" width="7" height="7" rx="1.5" />
                </svg>
              </div>
              <h2 className="bc-placeholder__title">n8n Integration</h2>
              <p className="bc-placeholder__text">
                n8n workflow automation will be available here.
              </p>
            </div>
          </div>
        )}
        {view === "marketplace" && (
          <div className="bc-layout__placeholder">
            <div className="bc-placeholder">
              <div className="bc-placeholder__icon">
                <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round" strokeLinejoin="round">
                  <path d="M3 9l9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z" />
                  <polyline points="9 22 9 12 15 12 15 22" />
                </svg>
              </div>
              <h2 className="bc-placeholder__title">Marketplace</h2>
              <p className="bc-placeholder__text">
                Browse and install community workflows and plugins.
              </p>
            </div>
          </div>
        )}
      </main>
    </div>
  )
}
