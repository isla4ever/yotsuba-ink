import { useEffect, useState } from "react"
import {
  extractVolumeReferenceContext,
  type VolumeReferenceContext,
} from "../lib/phase32Volumes"
import { getPhase32CurrentArtifact } from "../services/runApi"

type ContextState = {
  context: VolumeReferenceContext
  error: string
  loading: boolean
}

const EMPTY_CONTEXT: VolumeReferenceContext = { cast: {}, parts: {} }

export function usePhase32VolumeContext(
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
      getPhase32CurrentArtifact(runId, "book_architecture", controller.signal),
      getPhase32CurrentArtifact(runId, "cast", controller.signal),
    ])
      .then(([architecture, cast]) => {
        if (controller.signal.aborted) return
        setState({
          context: extractVolumeReferenceContext(
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
          context: EMPTY_CONTEXT,
          error:
            reason instanceof Error
              ? reason.message
              : "卷册上游 Part 与人物引用读取失败",
          loading: false,
        })
      })
    return () => controller.abort()
  }, [authorityRevision, enabled, runId])

  return state
}
