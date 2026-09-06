import { useCallback, useEffect, useRef, useState } from "react"
import type {
  Phase32ArtifactDraft,
  Phase32CurrentArtifact,
} from "../contracts/run"
import {
  getPhase32ArtifactDraft,
  getPhase32CurrentArtifact,
  RunApiError,
  savePhase32ArtifactDraft,
} from "../services/runApi"

export type Phase32DraftStatus = "idle" | "loading" | "empty" | "clean" | "dirty" | "saving" | "saved" | "readonly" | "error"

type DraftState = {
  bindingKey: string
  current: Phase32CurrentArtifact | null
  draftRef: string
  error: string
  localRevision: number
  payload: Record<string, unknown> | null
  savedRevision: number
  status: Phase32DraftStatus
}

const INITIAL_STATE: DraftState = {
  bindingKey: "",
  current: null,
  draftRef: "",
  error: "",
  localRevision: 0,
  payload: null,
  savedRevision: 0,
  status: "idle",
}

export function usePhase32ArtifactDraft(
  runId: string,
  stageId: string,
  authorityRevision: string,
  enabled = true,
  unitRef = "",
) {
  const [reloadRevision, setReloadRevision] = useState(0)
  const [state, setState] = useState<DraftState>(INITIAL_STATE)
  const stateRef = useRef(state)
  stateRef.current = state

  const reload = useCallback(() => {
    setReloadRevision((value) => value + 1)
  }, [])

  useEffect(() => {
    if (!runId || !stageId || !enabled) {
      setState({ ...INITIAL_STATE, status: enabled ? "idle" : "empty" })
      return undefined
    }
    const controller = new AbortController()
    setState({ ...INITIAL_STATE, status: "loading" })
    void getPhase32CurrentArtifact(runId, stageId, controller.signal, unitRef)
      .then(async (current) => {
        const decision = current.pending_decision
        const bindingKey =
          decision && decision.domain_revision !== null
            ? [
                runId,
                decision.decision_id,
                decision.domain_revision,
                current.artifact_ref,
              ].join("\u0000")
            : `${runId}\u0000${current.artifact_ref}`
        let draft: Phase32ArtifactDraft | null = null
        if (current.editable && decision) {
          draft = await getPhase32ArtifactDraft(
            runId,
            decision.decision_id,
            controller.signal,
          )
        }
        if (controller.signal.aborted) return
        setState({
          bindingKey,
          current,
          draftRef: draft?.draft_ref ?? "",
          error: "",
          localRevision: 0,
          payload: draft?.payload ?? current.payload,
          savedRevision: 0,
          status: current.editable ? (draft ? "saved" : "clean") : "readonly",
        })
      })
      .catch((reason) => {
        if (controller.signal.aborted) return
        if (reason instanceof RunApiError && reason.status === 404) {
          setState({ ...INITIAL_STATE, status: "empty" })
          return
        }
        setState({
          ...INITIAL_STATE,
          error: errorMessage(reason),
          status: "error",
        })
      })
    return () => controller.abort()
  }, [authorityRevision, enabled, reloadRevision, runId, stageId, unitRef])

  const persist = useCallback(async (snapshot: DraftState) => {
    const decision = snapshot.current?.pending_decision
    if (
      !snapshot.current?.editable ||
      !decision ||
      decision.domain_revision === null ||
      !snapshot.payload
    ) {
      throw new Error("当前 Artifact 不允许保存作者草稿")
    }
    setState((current) =>
      current.bindingKey === snapshot.bindingKey
        ? { ...current, error: "", status: "saving" }
        : current,
    )
    try {
      const saved = await savePhase32ArtifactDraft(
        snapshot.current.run_id,
        decision.decision_id,
        decision.domain_revision,
        snapshot.current.artifact_ref,
        snapshot.payload,
      )
      setState((current) => {
        if (current.bindingKey !== snapshot.bindingKey) return current
        const caughtUp = current.localRevision === snapshot.localRevision
        return {
          ...current,
          draftRef: saved.draft_ref,
          error: "",
          savedRevision: snapshot.localRevision,
          status: caughtUp ? "saved" : "dirty",
        }
      })
      return saved
    } catch (reason) {
      setState((current) =>
        current.bindingKey === snapshot.bindingKey
          ? { ...current, error: errorMessage(reason), status: "error" }
          : current,
      )
      throw reason
    }
  }, [])

  useEffect(() => {
    if (state.status !== "dirty" || state.localRevision === state.savedRevision)
      return undefined
    const snapshot = state
    const timer = window.setTimeout(() => {
      void persist(snapshot).catch(() => undefined)
    }, 650)
    return () => window.clearTimeout(timer)
  }, [persist, state])

  const change = useCallback((payload: Record<string, unknown>) => {
    setState((current) => {
      if (!current.current?.editable) return current
      return {
        ...current,
        error: "",
        localRevision: current.localRevision + 1,
        payload,
        status: "dirty",
      }
    })
  }, [])

  const flush = useCallback(async () => {
    const current = stateRef.current
    if (!current.current?.editable) return ""
    if (current.localRevision === current.savedRevision) return current.draftRef
    const saved = await persist(current)
    return saved.draft_ref
  }, [persist])

  return {
    change,
    current: state.current,
    draftRef: state.draftRef,
    error: state.error,
    flush,
    loading: state.status === "loading",
    payload: state.payload,
    reload,
    status: state.status,
  }
}

function errorMessage(reason: unknown) {
  return reason instanceof Error
    ? reason.message
    : "阶段 Artifact 读取或保存失败"
}
