import { useEffect, useState } from "react"
import {
  EMPTY_SCREENPLAY_CONTEXT,
  extractScreenplayReferenceContext,
  type ScreenplayReferenceContext,
} from "../lib/phase32Screenplay"
import { getPhase32CurrentArtifact } from "../services/runApi"

type ContextState = {
  context: ScreenplayReferenceContext
  error: string
  loading: boolean
}

export function usePhase32ScreenplayContext(
  runId: string,
  authorityRevision: string,
  enabled = true,
) {
  const [state, setState] = useState<ContextState>({
    context: EMPTY_SCREENPLAY_CONTEXT,
    error: "",
    loading: false,
  })

  useEffect(() => {
    if (!enabled || !runId) {
      setState({
        context: EMPTY_SCREENPLAY_CONTEXT,
        error: "",
        loading: false,
      })
      return undefined
    }
    const controller = new AbortController()
    setState((current) => ({ ...current, error: "", loading: true }))
    void Promise.all([
      getPhase32CurrentArtifact(runId, "scene_deck", controller.signal),
      getPhase32CurrentArtifact(runId, "cast", controller.signal),
    ])
      .then(([sceneDeck, cast]) => {
        if (controller.signal.aborted) return
        setState({
          context: extractScreenplayReferenceContext(
            sceneDeck.payload,
            cast.payload,
          ),
          error: "",
          loading: false,
        })
      })
      .catch((reason) => {
        if (controller.signal.aborted) return
        setState({
          context: EMPTY_SCREENPLAY_CONTEXT,
          error:
            reason instanceof Error
              ? reason.message
              : "剧本正文上游场景调度与人物名册读取失败",
          loading: false,
        })
      })
    return () => controller.abort()
  }, [authorityRevision, enabled, runId])

  return state
}
