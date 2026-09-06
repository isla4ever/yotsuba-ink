import { useEffect, useState } from "react"
import {
  extractRollingDetailReferenceContext,
  type RollingDetailReferenceContext,
} from "../lib/phase32RollingDetail"
import { getPhase32CurrentArtifact } from "../services/runApi"

type ContextState = {
  context: RollingDetailReferenceContext
  error: string
  loading: boolean
}

const EMPTY_CONTEXT: RollingDetailReferenceContext = {
  cast: {},
  volumes: {},
  volumeCast: {},
}

export function usePhase32RollingDetailContext(
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
      getPhase32CurrentArtifact(runId, "volumes", controller.signal),
      getPhase32CurrentArtifact(runId, "cast", controller.signal),
    ])
      .then(([volumes, cast]) => {
        if (controller.signal.aborted) return
        setState({
          context: extractRollingDetailReferenceContext(
            volumes.payload,
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
              : "Rolling Detail 上游 Volume 与人物引用读取失败",
          loading: false,
        })
      })
    return () => controller.abort()
  }, [authorityRevision, enabled, runId])

  return state
}
