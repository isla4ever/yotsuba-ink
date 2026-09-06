import { useCallback, useEffect, useState } from "react"
import {
  parseBookDeliveryArtifact,
  verifyBookDeliveryBinding,
  type BookDeliveryArtifact,
  type BookDeliveryChapterRow,
  type BookDeliveryEnvelope,
} from "../lib/phase32BookDelivery"
import {
  BookDeliveryApiError,
  getBookDelivery,
} from "../services/bookDeliveryApi"
import type { Phase32DeliveryDependencyStatus } from "../contracts/phase32Delivery"
import { getPhase32CurrentArtifact } from "../services/runApi"

type DeliveryState = {
  artifact: BookDeliveryArtifact | null
  artifactRef: string
  artifactDigest: string
  envelope: BookDeliveryEnvelope | null
  manifest: BookDeliveryChapterRow[]
  loading: boolean
  error: string
  errorCode: string
  dependencyStatus: Phase32DeliveryDependencyStatus | ""
  deferredReason: string
  sourceArtifactRefs: string[]
}

const EMPTY_STATE: DeliveryState = {
  artifact: null,
  artifactRef: "",
  artifactDigest: "",
  envelope: null,
  manifest: [],
  loading: false,
  error: "",
  errorCode: "",
  dependencyStatus: "",
  deferredReason: "",
  sourceArtifactRefs: [],
}

export function usePhase32BookDelivery(
  runId: string,
  authorityRevision: string,
  enabled = true,
) {
  const [reloadToken, setReloadToken] = useState(0)
  const [state, setState] = useState<DeliveryState>(EMPTY_STATE)
  const reload = useCallback(() => setReloadToken((value) => value + 1), [])

  useEffect(() => {
    if (!enabled || !runId) {
      setState(EMPTY_STATE)
      return undefined
    }
    const controller = new AbortController()
    setState((current) => ({
      ...current,
      error: "",
      errorCode: "",
      dependencyStatus: "",
      deferredReason: "",
      sourceArtifactRefs: [],
      loading: true,
    }))
    void getBookDelivery(runId, controller.signal)
      .then(async (envelope) => {
        const current = await getPhase32CurrentArtifact(
          runId,
          "export",
          controller.signal,
        )
        const artifact = parseBookDeliveryArtifact(current.payload)
        const bindingError = verifyBookDeliveryBinding(
          artifact,
          envelope,
          current.artifact_ref,
          current.payload_digest,
        )
        if (bindingError) throw new Error(bindingError)
        if (controller.signal.aborted) return
        setState({
          artifact,
          artifactRef: current.artifact_ref,
          artifactDigest: current.payload_digest,
          envelope,
          manifest: envelope.receipts[0]?.chapter_manifest ?? [],
          loading: false,
          error: "",
          errorCode: "",
          dependencyStatus: envelope.dependencyStatus,
          deferredReason: envelope.deferredReason,
          sourceArtifactRefs: envelope.sourceArtifactRefs,
        })
      })
      .catch((reason) => {
        if (controller.signal.aborted) return
        const apiError = reason instanceof BookDeliveryApiError ? reason : null
        setState({
          ...EMPTY_STATE,
          error:
            reason instanceof Error
              ? reason.message
              : "成书文件与正文版本清单读取失败",
          errorCode: apiError?.code ?? "",
          dependencyStatus: apiError?.dependencyStatus ?? "",
          deferredReason: apiError?.deferredReason ?? "",
          sourceArtifactRefs: apiError?.sourceArtifactRefs ?? [],
        })
      })
    return () => controller.abort()
  }, [authorityRevision, enabled, reloadToken, runId])

  return { ...state, reload }
}
