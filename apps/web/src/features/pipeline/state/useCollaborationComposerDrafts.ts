import { useCallback, useState } from "react"

export function useCollaborationComposerDrafts(activeThreadId: string) {
  const [drafts, setDrafts] = useState<Record<string, string>>({})
  const composerDraft = activeThreadId ? (drafts[activeThreadId] ?? "") : ""

  const setComposerDraft = useCallback(
    (value: string) => {
      if (!activeThreadId) return
      setDrafts((current) =>
        current[activeThreadId] === value
          ? current
          : { ...current, [activeThreadId]: value },
      )
    },
    [activeThreadId],
  )

  const clearComposerDraft = useCallback((threadId: string) => {
    if (!threadId) return
    setDrafts((current) =>
      current[threadId] ? { ...current, [threadId]: "" } : current,
    )
  }, [])

  const restoreComposerDraft = useCallback(
    (threadId: string, value: string) => {
      if (!threadId || !value) return
      setDrafts((current) =>
        current[threadId] ? current : { ...current, [threadId]: value },
      )
    },
    [],
  )

  const forgetComposerDraft = useCallback((threadId: string) => {
    setDrafts((current) => {
      if (!(threadId in current)) return current
      const next = { ...current }
      delete next[threadId]
      return next
    })
  }, [])

  const hasComposerDraft = useCallback(
    (threadId: string) => Boolean(drafts[threadId]?.trim()),
    [drafts],
  )

  return {
    clearComposerDraft,
    composerDraft,
    forgetComposerDraft,
    hasComposerDraft,
    restoreComposerDraft,
    setComposerDraft,
  }
}
