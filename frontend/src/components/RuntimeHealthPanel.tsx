// Biocraft-Spark — Runtime Health dashboard panel
//
// First real Phase 2 UI slice: verifies the Django backend link by calling the
// four backend /debug/ping-* endpoints and rendering their live status.

import { useRuntimeHealth, type OverallStatus } from "../hooks/useRuntimeHealth"
import type { RuntimeCheckResult } from "../lib/api"
import "./RuntimeHealthPanel.css"

const OVERALL_LABEL: Record<OverallStatus, string> = {
	healthy: "All Systems Operational",
	degraded: "Degraded",
	down: "Unavailable",
	unknown: "Checking...",
}

function formatTime(date: Date | null): string {
	if (!date) return "—"
	return date.toLocaleTimeString([], {
		hour: "2-digit",
		minute: "2-digit",
		second: "2-digit",
	})
}

function HealthCard({ result }: { result: RuntimeCheckResult }) {
	const state = result.ok ? "ok" : "fail"
	return (
		<article className={`bc-card bc-card--${state}`}>
			<header className="bc-card__head">
				<span className={`bc-dot bc-dot--${state}`} aria-hidden="true" />
				<h3 className="bc-card__title">{result.label}</h3>
				<span className="bc-card__latency">{result.latencyMs} ms</span>
			</header>
			<p className="bc-card__desc">{result.description}</p>
			<p className={`bc-card__detail bc-card__detail--${state}`}>
				{result.ok ? "✓ " : "✕ "}
				{result.detail}
			</p>
		</article>
	)
}

export interface RuntimeHealthPanelProps {
	/** Poll interval in ms. Pass 0 to disable auto-refresh. Default 15s. */
	pollMs?: number
}

export function RuntimeHealthPanel({ pollMs = 15000 }: RuntimeHealthPanelProps) {
	const { results, loading, lastUpdated, overall, refresh } =
		useRuntimeHealth(pollMs)

	return (
		<section className="bc-health" aria-label="Runtime health">
			<header className="bc-health__head">
				<div className="bc-health__titles">
					<h2 className="bc-health__title">Runtime Health</h2>
					<p className="bc-health__subtitle">Biocraft-Spark Core Runtime</p>
				</div>
				<div className={`bc-health__status bc-health__status--${overall}`}>
					<span className={`bc-dot bc-dot--${overall}`} aria-hidden="true" />
					{OVERALL_LABEL[overall]}
				</div>
			</header>

			<div className="bc-health__grid">
				{results.length === 0 && loading
					? Array.from({ length: 4 }).map((_, i) => (
							<article key={i} className="bc-card bc-card--skeleton" />
						))
					: results.map((r) => <HealthCard key={r.key} result={r} />)}
			</div>

			<footer className="bc-health__foot">
				<span className="bc-health__updated">
					Last check: {formatTime(lastUpdated)}
				</span>
				<button
					type="button"
					className="bc-btn"
					onClick={() => void refresh()}
					disabled={loading}
				>
					{loading ? "Checking..." : "Refresh"}
				</button>
			</footer>
		</section>
	)
}

export default RuntimeHealthPanel
