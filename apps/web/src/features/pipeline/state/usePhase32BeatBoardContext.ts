import { useEffect, useState } from "react"
import {
  EMPTY_BEAT_BOARD_CONTEXT,
  extractBeatBoardReferenceContext,
  type BeatBoardReferenceContext,
} from "../lib/phase32BeatBoard"
import { getPhase32CurrentArtifact } from "../services/runApi"

type ContextState = {
  context: BeatBoardReferenceContext
  error: string
  loading: boolean
}

export function usePhase32BeatBoardContext(
  runId: string,
  authorityRevision: string,
  enabled = true,
) {
  const [state, setState] = useState<ContextState>({
    context: EMPTY_BEAT_BOARD_CONTEXT,
    error: "",
    loading: false,
  })

  useEffect(() => {
    if (!enabled || !runId) {
      setState({
        context: EMPTY_BEAT_BOARD_CONTEXT,
        error: "",
        loading: false,
      })
      return undefined
    }
    const controller = new AbortController()
    setState((current) => ({ ...current, error: "", loading: true }))
    void Promise.all([
      getPhase32CurrentArtifact(runId, "brief", controller.signal),
      getPhase32CurrentArtifact(runId, "cast", controller.signal),
    ])
      .then(([brief, cast]) => {
        if (controller.signal.aborted) return
        setState({
          context: extractBeatBoardReferenceContext(
            brief.payload,
            cast.payload,
          ),
          error: "",
          loading: false,
        })
      })
      .catch((reason) => {
        if (controller.signal.aborted) return
        setState({
          context: EMPTY_BEAT_BOARD_CONTEXT,
          error:
            reason instanceof Error
              ? reason.message
              : "节拍上游样片 Brief 与人物名册读取失败",
          loading: false,
        })
      })
    return () => controller.abort()
  }, [authorityRevision, enabled, runId])

  return state
}
