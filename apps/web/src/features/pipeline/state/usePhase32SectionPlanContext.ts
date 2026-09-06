import { useEffect, useState } from "react"
import {
  extractSectionPlanReferenceContext,
  type SectionPlanReferenceContext,
} from "../lib/phase32SectionPlan"
import { getPhase32CurrentArtifact } from "../services/runApi"

type ContextState = {
  context: SectionPlanReferenceContext
  error: string
  loading: boolean
}

const EMPTY_CONTEXT: SectionPlanReferenceContext = { cast: {}, promises: {} }

export function usePhase32SectionPlanContext(
  runId: string,
  authorityRevision: string,
  enabled = true,
) {
  const [state, setState] = useState<ContextState>({
    context: EMPTY_CONTEXT,
    error: "",
    loading: false,
  })

  useEffect(() => {
    if (!enabled || !runId) {
      setState({ context: EMPTY_CONTEXT, error: "", loading: false })
      return undefined
    }
    const controller = new AbortController()
    setState((current) => ({ ...current, error: "", loading: true }))
    void Promise.all([
      getPhase32CurrentArtifact(runId, "story_map", controller.signal),
      getPhase32CurrentArtifact(runId, "cast", controller.signal),
    ])
      .then(([storyMap, cast]) => {
        if (controller.signal.aborted) return
        setState({
          context: extractSectionPlanReferenceContext(
            storyMap.payload,
            cast.payload,
          ),
          error: "",
          loading: false,
        })
      })
      .catch((reason) => {
        if (controller.signal.aborted) return
        setState({
          context: EMPTY_CONTEXT,
          error:
            reason instanceof Error
              ? reason.message
              : "章节计划上游故事地图与人物引用读取失败",
          loading: false,
        })
      })
    return () => controller.abort()
  }, [authorityRevision, enabled, runId])

  return state
}
