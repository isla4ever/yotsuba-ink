import { useCallback, useEffect, useRef, useState } from "react"
import type { Phase32CurrentArtifact } from "../contracts/run"
import { getPhase32CurrentArtifact, RunApiError } from "../services/runApi"

type MonitorArtifactState = {
  artifact: Phase32CurrentArtifact | null
  error: string
  loading: boolean
  refreshing: boolean
}

const EMPTY_STATE: MonitorArtifactState = {
  artifact: null,
  error: "",
  loading: false,
  refreshing: false,
}

export function usePhase32MonitorArtifact({
  authorityRevision,
  runId,
  stageId,
  unitRef,
}: {
  authorityRevision: string
  runId: string
  stageId: string
  unitRef: string
}) {
  const cacheRef = useRef(new Map<string, Phase32CurrentArtifact>())
  const [reloadRevision, setReloadRevision] = useState(0)
  const [state, setState] = useState<MonitorArtifactState>(EMPTY_STATE)
  const key = [runId, stageId, unitRef].join("\u0000")

  useEffect(() => {
    if (!runId || !stageId) {
      setState(EMPTY_STATE)
      return undefined
    }
    const controller = new AbortController()
    const cached = cacheRef.current.get(key) ?? null
    setState({
      artifact: cached,
      error: "",
      loading: !cached,
      refreshing: Boolean(cached),
    })

    void getPhase32CurrentArtifact(runId, stageId, controller.signal, unitRef)
      .then((artifact) => {
        if (controller.signal.aborted) return
        cacheRef.current.set(key, artifact)
        setState({ artifact, error: "", loading: false, refreshing: false })
      })
      .catch((reason: unknown) => {
        if (controller.signal.aborted) return
        if (reason instanceof RunApiError && reason.status === 404) {
          cacheRef.current.delete(key)
          setState(EMPTY_STATE)
          return
        }
        setState({
          artifact: cached,
          error:
            reason instanceof Error
              ? reason.message
              : "阶段内容读取失败，请稍后重试。",
          loading: false,
          refreshing: false,
        })
      })
    return () => controller.abort()
  }, [authorityRevision, key, reloadRevision, runId, stageId, unitRef])

  const reload = useCallback(() => {
    setReloadRevision((value) => value + 1)
  }, [])

  return { ...state, reload }
}
