// Biocraft-Spark — runtime health polling hook

import { useCallback, useEffect, useRef, useState } from "react"
import { runAllChecks, type RuntimeCheckResult } from "../lib/api"

export type OverallStatus = "healthy" | "degraded" | "down" | "unknown"

export interface RuntimeHealthState {
	results: RuntimeCheckResult[]
	loading: boolean
	lastUpdated: Date | null
	overall: OverallStatus
	refresh: () => void
}

function deriveOverall(results: RuntimeCheckResult[]): OverallStatus {
	if (results.length === 0) return "unknown"
	const okCount = results.filter((r) => r.ok).length
	if (okCount === results.length) return "healthy"
	if (okCount === 0) return "down"
	return "degraded"
}

/**
 * Poll the backend runtime health endpoints.
 * @param pollMs Interval in ms. Pass 0 or a negative number to disable polling.
 */
export function useRuntimeHealth(pollMs = 15000): RuntimeHealthState {
	const [results, setResults] = useState<RuntimeCheckResult[]>([])
	const [loading, setLoading] = useState(true)
	const [lastUpdated, setLastUpdated] = useState<Date | null>(null)
	const inFlight = useRef(false)

	const refresh = useCallback(async () => {
		if (inFlight.current) return
		inFlight.current = true
		setLoading(true)
		try {
			const next = await runAllChecks()
			setResults(next)
			setLastUpdated(new Date())
		} finally {
			setLoading(false)
			inFlight.current = false
		}
	}, [])

	useEffect(() => {
		let cancelled = false
		void refresh()
		if (pollMs <= 0) return
		const id = setInterval(() => {
			if (!cancelled) void refresh()
		}, pollMs)
		return () => {
			cancelled = true
			clearInterval(id)
		}
	}, [refresh, pollMs])

	return {
		results,
		loading,
		lastUpdated,
		overall: deriveOverall(results),
		refresh,
	}
}
