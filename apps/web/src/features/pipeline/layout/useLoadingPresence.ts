import { useEffect, useState } from "react"

const DEFAULT_EXIT_MS = 220

export function useLoadingPresence(loading: boolean, exitMs = DEFAULT_EXIT_MS) {
  const [visible, setVisible] = useState(loading)
  const [exiting, setExiting] = useState(false)

  useEffect(() => {
    if (loading) {
      setVisible(true)
      setExiting(false)
      return
    }

    if (!visible) return
    const prefersReducedMotion = window.matchMedia(
      "(prefers-reduced-motion: reduce)",
    ).matches
    if (prefersReducedMotion || exitMs === 0) {
      setVisible(false)
      setExiting(false)
      return
    }
    setExiting(true)
    const timer = window.setTimeout(() => {
      setVisible(false)
      setExiting(false)
    }, exitMs)
    return () => window.clearTimeout(timer)
  }, [exitMs, loading, visible])

  return {
    exiting: !loading && exiting,
    visible: loading || visible,
  }
}
