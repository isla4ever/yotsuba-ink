import { useCallback, useEffect, useState } from "react"
import type { RunArtifactRecord } from "../contracts/run"
import type { StageDecision } from "../lib/stageDecision"
import {
  getStageArtifactDraft,
  saveStageArtifactDraft,
} from "../services/runApi"
import {
  STAGE_DRAFT_UPDATED_EVENT,
  type StageDraftUpdatedDetail,
} from "./stageDraftEvents"

export type StageDraftStatus = "idle" | "loading" | "clean" | "dirty" | "saving" | "saved" | "error"

type StageArtifactDraftSource = Pick<RunArtifactRecord, "artifact_id" | "payload">

type DraftState = {
  artifact: Record<string, unknown> | null
  bindingKey: string
  error: string
  localRevision: number
  status: StageDraftStatus
}

const idleState: DraftState = {
  artifact: null,
  bindingKey: "",
  error: "",
  localRevision: 0,
  status: "idle",
}

export function useStageArtifactDraft(
  runId: string,
  decision: StageDecision | null,
  source: StageArtifactDraftSource | undefined,
) {
  const [externalRevision, setExternalRevision] = useState(0)
  const decisionId = decision?.decisionId ?? ""
  const domainRevision = decision?.domainRevision ?? -1
  const sourceArtifactId = source?.artifact_id ?? ""
  const bindingKey =
    decision && source
      ? `${runId}\u0000${decision.decisionId}\u0000${decision.domainRevision}\u0000${source.artifact_id}`
      : ""
  const [state, setState] = useState<DraftState>(idleState)

  useEffect(() => {
    if (
      !runId ||
      !decision ||
      !source ||
      source.artifact_id !== decision.artifactRef
    ) {
      setState({ ...idleState, artifact: source?.payload ?? null })
      return undefined
    }
    const controller = new AbortController()
    setState({
      artifact: source.payload,
      bindingKey,
      error: "",
      localRevision: 0,
      status: "loading",
    })
    void getStageArtifactDraft(runId, decision.decisionId, controller.signal)
      .then((record) => {
        setState((current) =>
          current.bindingKey === bindingKey && current.localRevision === 0
            ? {
                artifact: record?.payload ?? source.payload,
                bindingKey,
                error: "",
                localRevision: 0,
                status: record ? "saved" : "clean",
              }
            : current,
        )
      })
      .catch((reason) => {
        if (controller.signal.aborted) return
        setState((current) =>
          current.bindingKey === bindingKey
            ? { ...current, error: errorMessage(reason), status: "error" }
            : current,
        )
      })
    return () => controller.abort()
  }, [bindingKey, externalRevision, runId])

  useEffect(() => {
    const refresh = (event: Event) => {
      const detail = (event as CustomEvent<StageDraftUpdatedDetail>).detail
      if (detail?.runId === runId && detail.stageId === decision?.stageId)
        setExternalRevision((current) => current + 1)
    }
    window.addEventListener(STAGE_DRAFT_UPDATED_EVENT, refresh)
    return () => window.removeEventListener(STAGE_DRAFT_UPDATED_EVENT, refresh)
  }, [decision?.stageId, runId])

  useEffect(() => {
    if (
      !decision ||
      !source ||
      !state.artifact ||
      state.bindingKey !== bindingKey ||
      state.status !== "dirty"
    ) {
      return undefined
    }
    const revision = state.localRevision
    const artifact = state.artifact
    const timer = window.setTimeout(() => {
      setState((current) =>
        current.bindingKey === bindingKey && current.localRevision === revision
          ? { ...current, error: "", status: "saving" }
          : current,
      )
      void saveStageArtifactDraft(
        runId,
        decisionId,
        domainRevision,
        sourceArtifactId,
        artifact,
      )
        .then(() => {
          setState((current) =>
            current.bindingKey === bindingKey
              ? {
                  ...current,
                  error: "",
                  status:
                    current.localRevision === revision ? "saved" : "dirty",
                }
              : current,
          )
        })
        .catch((reason) => {
          setState((current) =>
            current.bindingKey === bindingKey &&
            current.localRevision === revision
              ? { ...current, error: errorMessage(reason), status: "error" }
              : current,
          )
        })
    }, 650)
    return () => window.clearTimeout(timer)
  }, [bindingKey, decisionId, domainRevision, runId, sourceArtifactId, state])

  const change = useCallback(
    (artifact: Record<string, unknown>) => {
      if (!bindingKey) return
      setState((current) => ({
        artifact,
        bindingKey,
        error: "",
        localRevision:
          current.bindingKey === bindingKey ? current.localRevision + 1 : 1,
        status: "dirty",
      }))
    },
    [bindingKey],
  )

  return {
    artifact:
      state.bindingKey === bindingKey || !bindingKey
        ? (state.artifact ?? source?.payload ?? null)
        : (source?.payload ?? null),
    change,
    error: state.bindingKey === bindingKey ? state.error : "",
    status: state.bindingKey === bindingKey ? state.status : "idle",
  }
}

function errorMessage(reason: unknown) {
  return reason instanceof Error ? reason.message : "阶段草稿保存失败"
}
