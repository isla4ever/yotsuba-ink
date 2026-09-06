import { useEffect, useState } from "react"
import {
  EMPTY_SHORT_PROSE_CONTEXT,
  extractShortProseReferenceContext,
  type ShortProseReferenceContext,
} from "../lib/phase32ShortProse"
import { getPhase32CurrentArtifact } from "../services/runApi"

type ContextState = {
  context: ShortProseReferenceContext
  error: string
  loading: boolean
}

export function usePhase32ShortProseContext(
  runId: string,
  authorityRevision: string,
  enabled = true,
) {
  const [state, setState] = useState<ContextState>({
    context: EMPTY_SHORT_PROSE_CONTEXT,
    error: "",
    loading: false,
  })

  useEffect(() => {
    if (!enabled || !runId) {
      setState({
        context: EMPTY_SHORT_PROSE_CONTEXT,
        error: "",
        loading: false,
      })
      return undefined
    }
    const controller = new AbortController()
    setState((current) => ({ ...current, error: "", loading: true }))
    void Promise.all([
      getPhase32CurrentArtifact(runId, "section_plan", controller.signal),
      getPhase32CurrentArtifact(runId, "cast", controller.signal),
      getPhase32CurrentArtifact(runId, "story_map", controller.signal),
    ])
      .then(([sectionPlan, cast, storyMap]) => {
        if (controller.signal.aborted) return
        setState({
          context: extractShortProseReferenceContext(
            sectionPlan.payload,
            cast.payload,
            storyMap.payload,
          ),
          error: "",
          loading: false,
        })
      })
      .catch((reason) => {
        if (controller.signal.aborted) return
        setState({
          context: EMPTY_SHORT_PROSE_CONTEXT,
          error:
            reason instanceof Error
              ? reason.message
              : "正文上游单元计划、人物名册与故事地图读取失败",
          loading: false,
        })
      })
    return () => controller.abort()
  }, [authorityRevision, enabled, runId])

  return state
}
