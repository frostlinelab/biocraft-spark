import { useCallback, useEffect, useState } from "react"
import {
  fetchMarketplaceCatalog,
  installPlugin,
  uninstallPlugin,
  type MarketplacePlugin,
} from "../lib/api"
import "./Marketplace.css"

type FilterKey = "all" | "curated" | "installed"

const FILTERS: { key: FilterKey; label: string }[] = [
  { key: "all", label: "All" },
  { key: "curated", label: "✨ Beautiful Creatures" },
  { key: "installed", label: "Installed" },
]

// Emoji glyphs for the icon keys defined in BlockSpec (schema.py).
const ICON_GLYPH: Record<string, string> = {
  microscope: "🔬",
  beaker: "⚗️",
  dna: "🧬",
  filter: "⧂",
  wrench: "🔧",
  process: "▢",
  input: "↧",
  output: "↥",
  start: "▶",
  end: "■",
  builtin: "◆",
}

export default function Marketplace() {
  const [plugins, setPlugins] = useState<MarketplacePlugin[] | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [filter, setFilter] = useState<FilterKey>("all")
  const [installing, setInstalling] = useState<Set<string>>(new Set())
  const [toast, setToast] = useState<{ kind: "ok" | "err"; msg: string } | null>(null)

  const loadCatalog = useCallback(async () => {
    setLoading(true)
    setError(null)
    const res = await fetchMarketplaceCatalog()
    if (res == null) {
      setError("Failed to load marketplace catalog. Is the registry reachable?")
      setPlugins(null)
    } else {
      setPlugins(res.plugins)
    }
    setLoading(false)
  }, [])

  // Initial load — cancelled flag guards against setting state after unmount.
  useEffect(() => {
    let cancelled = false
    setLoading(true)
    void fetchMarketplaceCatalog().then((res) => {
      if (cancelled) return
      if (res == null) {
        setError("Failed to load marketplace catalog. Is the registry reachable?")
        setPlugins(null)
      } else {
        setPlugins(res.plugins)
      }
      setLoading(false)
    })
    return () => {
      cancelled = true
    }
  }, [])

  const flash = (kind: "ok" | "err", msg: string) => {
    setToast({ kind, msg })
    setTimeout(() => setToast(null), 3500)
  }

  const handleInstall = useCallback(
    async (p: MarketplacePlugin) => {
      setInstalling((prev) => new Set(prev).add(p.name))
      const res = await installPlugin({
        yaml_url: p.yaml_url,
        sha256: p.sha256 || undefined,
        author: p.author,
        curated: p.curated,
      })
      setInstalling((prev) => {
        const next = new Set(prev)
        next.delete(p.name)
        return next
      })
      if (res.ok) {
        flash("ok", `Installed ${p.name} ${p.version}`)
        await loadCatalog()
      } else {
        flash("err", res.error ?? `Failed to install ${p.name}`)
      }
    },
    [loadCatalog],
  )

  const handleUninstall = useCallback(
    async (p: MarketplacePlugin) => {
      setInstalling((prev) => new Set(prev).add(p.name))
      const res = await uninstallPlugin(p.name)
      setInstalling((prev) => {
        const next = new Set(prev)
        next.delete(p.name)
        return next
      })
      if (res.ok) {
        flash("ok", `Uninstalled ${p.name}`)
        await loadCatalog()
      } else {
        flash("err", res.error ?? `Failed to uninstall ${p.name}`)
      }
    },
    [loadCatalog],
  )

  const visible = (plugins ?? []).filter((p) => {
    if (filter === "curated") return p.curated
    if (filter === "installed") return p.installed_version != null
    return true
  })

  return (
    <div className="bc-market">
      <header className="bc-market__head">
        <h1 className="bc-market__title">Marketplace</h1>
        <p className="bc-market__subtitle">
          Browse and install community plugins. Curated picks live in the Beautiful Creatures collection.
        </p>
      </header>

      <div className="bc-market__filters" role="tablist">
        {FILTERS.map((f) => (
          <button
            key={f.key}
            type="button"
            role="tab"
            aria-selected={filter === f.key}
            className={`bc-market__filter${filter === f.key ? " bc-market__filter--active" : ""}`}
            onClick={() => setFilter(f.key)}
          >
            {f.label}
          </button>
        ))}
      </div>

      {loading ? (
        <p className="bc-market__muted">Loading catalog…</p>
      ) : error ? (
        <p className="bc-market__error">{error}</p>
      ) : visible.length === 0 ? (
        <p className="bc-market__muted">No plugins in this view.</p>
      ) : (
        <div className="bc-market__grid">
          {visible.map((p) => (
            <PluginCard
              key={p.name}
              plugin={p}
              busy={installing.has(p.name)}
              onInstall={() => handleInstall(p)}
              onUninstall={() => handleUninstall(p)}
            />
          ))}
        </div>
      )}

      <p className="bc-market__hint">
        Newly installed blocks appear in the workflow node palette after refreshing the page.
      </p>

      {toast && (
        <div className={`bc-market__toast bc-market__toast--${toast.kind}`} role="status">
          {toast.msg}
        </div>
      )}
    </div>
  )
}

function PluginCard({
  plugin,
  busy,
  onInstall,
  onUninstall,
}: {
  plugin: MarketplacePlugin
  busy: boolean
  onInstall: () => void
  onUninstall: () => void
}) {
  const installed = plugin.installed_version != null
  const updatable = installed && plugin.installed_version !== plugin.version
  const managed = plugin.managed

  return (
    <div className="bc-market__card">
      <div className="bc-market__card-head">
        <span className="bc-market__icon" aria-hidden>
          {ICON_GLYPH[plugin.icon] ?? "▢"}
        </span>
        <div className="bc-market__card-titles">
          <span className="bc-market__name">{plugin.name}</span>
          <span className="bc-market__version">v{plugin.version}</span>
        </div>
        {plugin.curated && (
          <span className="bc-market__badge" title="Beautiful Creatures — curated">✨</span>
        )}
      </div>

      <p className="bc-market__desc">{plugin.description || "No description."}</p>
      <p className="bc-market__author">by {plugin.author || "official"}</p>

      <div className="bc-market__actions">
        {!installed && (
          <button
            type="button"
            className="bc-market__btn bc-market__btn--primary"
            disabled={busy}
            onClick={onInstall}
          >
            {busy ? "Installing…" : "Install"}
          </button>
        )}
        {installed && !updatable && (
          <span className="bc-market__installed">
            ✓ Installed{!managed ? " (built-in)" : ""}
          </span>
        )}
        {installed && updatable && (
          <button
            type="button"
            className="bc-market__btn bc-market__btn--primary"
            disabled={busy}
            onClick={onInstall}
          >
            {busy ? "Updating…" : `Update · v${plugin.installed_version} → v${plugin.version}`}
          </button>
        )}
        {managed && (
          <button
            type="button"
            className="bc-market__btn bc-market__btn--danger"
            disabled={busy}
            onClick={onUninstall}
          >
            {busy ? "Removing…" : "Uninstall"}
          </button>
        )}
      </div>
    </div>
  )
}
