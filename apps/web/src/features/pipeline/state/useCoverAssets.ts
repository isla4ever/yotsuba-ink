import { useEffect, useState } from "react"
import type { CoverAssetRecord } from "../contracts/coverAsset"
import { getCoverAssets } from "../services/coverAssetApi"

type CoverAssetState = {
  assets: CoverAssetRecord[]
  error: string
  generationAttempt: number
  status: "idle" | "loading" | "ready" | "error"
}

const idleState: CoverAssetState = {
  assets: [],
  error: "",
  generationAttempt: 0,
  status: "idle",
}

export function useCoverAssets(
  runId: string,
  enabled = true,
  authorityRevision = "",
) {
  const [state, setState] = useState<CoverAssetState>(idleState)

  useEffect(() => {
    if (!runId || !enabled) {
      setState(idleState)
      return undefined
    }
    const controller = new AbortController()
    setState({ ...idleState, status: "loading" })
    void getCoverAssets(runId, controller.signal)
      .then((collection) =>
        setState({
          assets: collection.items,
          error: "",
          generationAttempt: collection.generation_attempt,
          status: "ready",
        }),
      )
      .catch((reason) => {
        if (controller.signal.aborted) return
        setState({
          ...idleState,
          error: reason instanceof Error ? reason.message : "封面资产读取失败",
          status: "error",
        })
      })
    return () => controller.abort()
  }, [authorityRevision, enabled, runId])

  return state
}
