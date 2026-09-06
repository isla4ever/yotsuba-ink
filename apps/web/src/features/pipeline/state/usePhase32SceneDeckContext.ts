import { useEffect, useState } from "react"
import {
  EMPTY_SCENE_DECK_CONTEXT,
  extractSceneDeckReferenceContext,
  type SceneDeckReferenceContext,
} from "../lib/phase32SceneDeck"
import { getPhase32CurrentArtifact } from "../services/runApi"

type ContextState = {
  context: SceneDeckReferenceContext
  error: string
  loading: boolean
}

export function usePhase32SceneDeckContext(
  runId: string,
  authorityRevision: string,
  enabled = true,
) {
  const [state, setState] = useState<ContextState>({
    context: EMPTY_SCENE_DECK_CONTEXT,
    error: "",
    loading: false,
  })

  useEffect(() => {
    if (!enabled || !runId) {
      setState({
        context: EMPTY_SCENE_DECK_CONTEXT,
        error: "",
        loading: false,
      })
      return undefined
    }
    const controller = new AbortController()
    setState((current) => ({ ...current, error: "", loading: true }))
    void Promise.all([
      getPhase32CurrentArtifact(runId, "beat_board", controller.signal),
      getPhase32CurrentArtifact(runId, "cast", controller.signal),
    ])
      .then(([beatBoard, cast]) => {
        if (controller.signal.aborted) return
        setState({
          context: extractSceneDeckReferenceContext(
            beatBoard.payload,
            cast.payload,
          ),
          error: "",
          loading: false,
        })
      })
      .catch((reason) => {
        if (controller.signal.aborted) return
        setState({
          context: EMPTY_SCENE_DECK_CONTEXT,
          error:
            reason instanceof Error
              ? reason.message
              : "场景调度上游 Beat Board 与人物名册读取失败",
          loading: false,
        })
      })
    return () => controller.abort()
  }, [authorityRevision, enabled, runId])

  return state
}
