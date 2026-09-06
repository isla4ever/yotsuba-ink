import { useCallback, useEffect, useState } from "react"
import {
  buildScriptDeliveryManifest,
  parseScriptDeliveryArtifact,
  verifyScriptDeliveryBinding,
  type ScriptDeliveryArtifact,
  type ScriptDeliveryEnvelope,
  type ScriptDeliverySceneRow,
} from "../lib/phase32ScriptDelivery"
import { ScriptDeliveryApiError } from "../services/scriptDeliveryApi"
import type { Phase32DeliveryDependencyStatus } from "../contracts/phase32Delivery"
import { getPhase32CurrentArtifact } from "../services/runApi"
import { getScriptDelivery } from "../services/scriptDeliveryApi"

type DeliveryState = {
  artifact: ScriptDeliveryArtifact | null
  artifactRef: string
  artifactDigest: string
  envelope: ScriptDeliveryEnvelope | null
  manifest: ScriptDeliverySceneRow[]
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

export function usePhase32ScriptDelivery(
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
    void getScriptDelivery(runId, controller.signal)
      .then(async (envelope) => {
        const current = await getPhase32CurrentArtifact(
          runId,
          "export",
          controller.signal,
        )
        const artifact = parseScriptDeliveryArtifact(current.payload)
        const bindingError = verifyScriptDeliveryBinding(
          artifact,
          envelope,
          current.artifact_ref,
          current.payload_digest,
        )
        if (bindingError) throw new Error(bindingError)
        const sceneArtifacts = await Promise.all(
          artifact.scene_refs.map((sceneRef) =>
            getPhase32CurrentArtifact(
              runId,
              "script",
              controller.signal,
              sceneRef,
            ),
          ),
        )
        if (controller.signal.aborted) return
        const scenes = Object.fromEntries(
          sceneArtifacts.map((scene) => [scene.unit_ref, scene.payload]),
        )
        setState({
          artifact,
          artifactRef: current.artifact_ref,
          artifactDigest: current.payload_digest,
          envelope,
          manifest: buildScriptDeliveryManifest(artifact, scenes),
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
        const apiError =
          reason instanceof ScriptDeliveryApiError ? reason : null
        setState({
          ...EMPTY_STATE,
          error:
            reason instanceof Error
              ? reason.message
              : "剧本交付文件与 Scene Manifest 读取失败",
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
