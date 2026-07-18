import { useState } from "react"
import Sidebar, { type NavView } from "./Sidebar"
import WorkflowCanvas from "./WorkflowCanvas"
import RuntimeHealthPanel from "./RuntimeHealthPanel"
import "./AppLayout.css"

export default function AppLayout() {
  const [view, setView] = useState<NavView>("workflows")

  return (
    <div className="bc-layout">
      <Sidebar active={view} onChange={setView} />
      <main className="bc-layout__main">
        {view === "workflows" && <WorkflowCanvas />}
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
      </main>
    </div>
  )
}
