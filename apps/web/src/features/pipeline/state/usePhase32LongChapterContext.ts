import { useEffect, useState } from "react"
import {
  EMPTY_LONG_CHAPTER_CONTEXT,
  extractLongChapterContext,
  type LongChapterContext,
} from "../lib/phase32LongChapter"
import { getPhase32CurrentArtifact } from "../services/runApi"

type ContextState = {
  context: LongChapterContext
  error: string
  loading: boolean
}

export function usePhase32LongChapterContext(
  runId: string,
  authorityRevision: string,
  enabled = true,
) {
  const [state, setState] = useState<ContextState>({
    context: EMPTY_LONG_CHAPTER_CONTEXT,
    error: "",
    loading: false,
  })

  useEffect(() => {
    if (!enabled || !runId) {
      setState({
        context: EMPTY_LONG_CHAPTER_CONTEXT,
        error: "",
        loading: false,
      })
      return undefined
    }
    const controller = new AbortController()
    setState((current) => ({ ...current, error: "", loading: true }))
    void Promise.all([
      getPhase32CurrentArtifact(runId, "rolling_detail", controller.signal),
      getPhase32CurrentArtifact(runId, "volumes", controller.signal),
      getPhase32CurrentArtifact(runId, "book_architecture", controller.signal),
      getPhase32CurrentArtifact(runId, "cast", controller.signal),
    ])
      .then(([detail, volumes, architecture, cast]) => {
        if (controller.signal.aborted) return
        setState({
          context: extractLongChapterContext(
            detail.payload,
            volumes.payload,
            architecture.payload,
            cast.payload,
          ),
          error: "",
          loading: false,
        })
      })
      .catch((reason) => {
        if (controller.signal.aborted) return
        setState({
          context: EMPTY_LONG_CHAPTER_CONTEXT,
          error:
            reason instanceof Error
              ? reason.message
              : "长篇章节的架构、卷册、细纲与人物上下文读取失败",
          loading: false,
        })
      })
    return () => controller.abort()
  }, [authorityRevision, enabled, runId])

  return state
}
