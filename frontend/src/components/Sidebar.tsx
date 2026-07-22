import type { ReactNode } from "react"
import logoUrl from "../assets/logo.png"
import "./Sidebar.css"

export type NavView = "dashboard" | "workflows" | "tasks" | "health" | "n8n" | "marketplace"

export interface NavItem {
  key: NavView
  label: string
  icon: ReactNode
  disabled?: boolean
}

interface SidebarProps {
  active: NavView
  items?: NavItem[]
  onChange: (key: NavView) => void
}

const DEFAULT_ITEMS: NavItem[] = [
  {
    key: "dashboard",
    label: "Dashboard",
    icon: <DashboardIcon />,
  },
  {
    key: "workflows",
    label: "Workflows",
    icon: <DAGIcon />,
  },
  {
    key: "tasks",
    label: "Task Runs",
    icon: <ListIcon />,
  },
  {
    key: "health",
    label: "Health Check",
    icon: <HeartIcon />,
  },
  {
    key: "n8n",
    label: "n8n",
    icon: <N8NIcon />,
    disabled: true,
  },
  {
    key: "marketplace",
    label: "Marketplace",
    icon: <MarketplaceIcon />,
  },
]

function DashboardIcon() {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
      <rect x="3" y="3" width="7" height="9" rx="1.5" />
      <rect x="14" y="3" width="7" height="5" rx="1.5" />
      <rect x="14" y="12" width="7" height="9" rx="1.5" />
      <rect x="3" y="16" width="7" height="5" rx="1.5" />
    </svg>
  )
}

function ListIcon() {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
      <line x1="8" y1="6" x2="21" y2="6" />
      <line x1="8" y1="12" x2="21" y2="12" />
      <line x1="8" y1="18" x2="21" y2="18" />
      <circle cx="4" cy="6" r="1.2" fill="currentColor" stroke="none" />
      <circle cx="4" cy="12" r="1.2" fill="currentColor" stroke="none" />
      <circle cx="4" cy="18" r="1.2" fill="currentColor" stroke="none" />
    </svg>
  )
}

function DAGIcon() {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
      <circle cx="12" cy="5" r="2.5" />
      <circle cx="5" cy="19" r="2.5" />
      <circle cx="19" cy="19" r="2.5" />
      <line x1="12" y1="7.5" x2="5" y2="16.5" />
      <line x1="12" y1="7.5" x2="19" y2="16.5" />
      <line x1="7.5" y1="19" x2="17.5" y2="19" />
    </svg>
  )
}

function HeartIcon() {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
      <path d="M20.84 4.61a5.5 5.5 0 0 0-7.78 0L12 5.67l-1.06-1.06a5.5 5.5 0 0 0-7.78 7.78l1.06 1.06L12 21.23l7.78-7.78 1.06-1.06a5.5 5.5 0 0 0 0-7.78z" />
    </svg>
  )
}

function N8NIcon() {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
      <rect x="3" y="3" width="7" height="7" rx="1.5" />
      <rect x="14" y="3" width="7" height="7" rx="1.5" />
      <rect x="3" y="14" width="7" height="7" rx="1.5" />
      <rect x="14" y="14" width="7" height="7" rx="1.5" />
    </svg>
  )
}

function MarketplaceIcon() {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
      <path d="M3 9l9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z" />
      <polyline points="9 22 9 12 15 12 15 22" />
    </svg>
  )
}

export default function Sidebar({ active, onChange, items = DEFAULT_ITEMS }: SidebarProps) {
  return (
    <aside className="bc-sidebar">
      <div className="bc-sidebar__brand">
        <img className="bc-sidebar__logo" src={logoUrl} alt="Biocraft Spark" />
        <span className="bc-sidebar__name">Biocraft Spark</span>
      </div>

      <nav className="bc-sidebar__nav">
        {items.map((item) => (
          <button
            key={item.key}
            type="button"
            className={`bc-sidebar__item${item.key === active ? " bc-sidebar__item--active" : ""}${item.disabled ? " bc-sidebar__item--disabled" : ""}`}
            onClick={() => !item.disabled && onChange(item.key)}
            disabled={item.disabled}
            title={item.disabled ? `${item.label} — coming soon` : item.label}
          >
            <span className="bc-sidebar__icon">{item.icon}</span>
            <span className="bc-sidebar__label">{item.label}</span>
            {item.disabled && <span className="bc-sidebar__badge">Soon</span>}
          </button>
        ))}
      </nav>

      <div className="bc-sidebar__footer">
        <span className="bc-sidebar__version">v0.1.0</span>
      </div>
    </aside>
  )
}
