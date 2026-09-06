import { useEffect, useState } from "react"
import type { Phase32CurrentArtifact } from "../contracts/run"
import { getPhase32CurrentArtifact } from "../services/runApi"

type Params = {
  enabled: boolean
  runId: string
  stageId: string
  unitRef?: string
}

export function usePhase32CollaborationSource({
  enabled,
  runId,
  stageId,
  unitRef = "",
}: Params) {
  const [artifact, setArtifact] = useState<Phase32CurrentArtifact | null>(null)
  const [error, setError] = useState("")
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    setArtifact(null)
    setError("")
    if (!enabled || !runId || !stageId) return undefined

    const controller = new AbortController()
    setLoading(true)
    void getPhase32CurrentArtifact(runId, stageId, controller.signal, unitRef)
      .then((current) => {
        if (!controller.signal.aborted) setArtifact(current)
      })
      .catch((cause: unknown) => {
        if (controller.signal.aborted) return
        setError(
          cause instanceof Error
            ? cause.message
            : "当前阶段内容读取失败，请稍后重试。",
        )
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false)
      })
    return () => controller.abort()
  }, [enabled, runId, stageId, unitRef])

  return { artifact, error, loading }
}
