import { useCallback, useEffect, useMemo, useRef, useState } from "react"
import type {
  AmendmentApplyReceipt,
  AmendmentApplyScope,
  AmendmentBranchReceipt,
  ArtifactAmendment,
  ArtifactImpactAnalysis,
} from "../contracts/artifactAmendment"
import type {
  Phase32CurrentArtifact,
  Phase32RunEnvelope,
} from "../contracts/run"
import {
  applyArtifactAmendment,
  createArtifactAmendment,
  createArtifactAmendmentBranch,
  getArtifactAmendmentBranch,
  getArtifactAmendmentImpact,
} from "../services/artifactAmendmentApi"

export type ArtifactAmendmentPhase = "idle" | "editing" | "review" | "previewing" | "impact" | "applying" | "restoring" | "applied" | "branching" | "successor"

type AmendmentState = {
  bindingKey: string
  phase: ArtifactAmendmentPhase
  payload: Record<string, unknown> | null
  authorNote: string
  scope: AmendmentApplyScope
  amendment: ArtifactAmendment | null
  impact: ArtifactImpactAnalysis | null
  applyReceipt: AmendmentApplyReceipt | null
  branchReceipt: AmendmentBranchReceipt | null
  targetRun: Phase32RunEnvelope | null
  error: string
}

const EMPTY_STATE: AmendmentState = {
  bindingKey: "",
  phase: "idle",
  payload: null,
  authorNote: "",
  scope: "affected_only",
  amendment: null,
  impact: null,
  applyReceipt: null,
  branchReceipt: null,
  targetRun: null,
  error: "",
}

type Options = {
  run: Phase32RunEnvelope | null
  stageId: string
  current: Phase32CurrentArtifact | null
  enabled?: boolean
  onSourceRunChanged?: () => Promise<unknown> | unknown
}

export function useArtifactAmendment({
  run,
  stageId,
  current,
  enabled = true,
  onSourceRunChanged,
}: Options) {
  const [state, setState] = useState<AmendmentState>(EMPTY_STATE)
  const [restoreRevision, setRestoreRevision] = useState(0)
  const operationRef = useRef(0)
  const keysRef = useRef({ create: "", apply: "", branch: "" })
  const runId = run?.definition.run_id ?? ""
  const activeAmendmentId = run?.read_model.active_amendment_id ?? ""
  const sourcePayload = current?.payload ?? null
  const bindingKey = [
    runId,
    current?.artifact_ref ?? "",
    activeAmendmentId,
    run?.read_model.updated_at ?? "",
  ].join("\u0000")
  const canStart = Boolean(
    enabled &&
      run &&
      current?.status === "committed" &&
      ["completed", "failed"].includes(run.read_model.status) &&
      !run.read_model.pending_decisions.length &&
      !activeAmendmentId,
  )

  useEffect(() => {
    const operation = ++operationRef.current
    keysRef.current = { create: "", apply: "", branch: "" }
    if (!enabled || !runId) {
      setState(EMPTY_STATE)
      return undefined
    }
    if (run?.read_model.status !== "needs_action" || !activeAmendmentId) {
      setState({ ...EMPTY_STATE, bindingKey })
      return undefined
    }

    const controller = new AbortController()
    setState({
      ...EMPTY_STATE,
      bindingKey,
      phase: "restoring",
    })
    void Promise.all([
      getArtifactAmendmentImpact(runId, activeAmendmentId, controller.signal),
      getArtifactAmendmentBranch(runId, activeAmendmentId, controller.signal),
    ])
      .then(([impact, branch]) => {
        if (controller.signal.aborted || operation !== operationRef.current)
          return
        if (!branch.apply_receipt)
          throw new Error("旧 Run 已进入 stale 状态，但服务端缺少正式修订回执")
        setState({
          ...EMPTY_STATE,
          bindingKey,
          phase: branch.receipt ? "successor" : "applied",
          impact,
          applyReceipt: branch.apply_receipt,
          branchReceipt: branch.receipt,
          targetRun: branch.target_run,
        })
      })
      .catch((reason) => {
        if (controller.signal.aborted || operation !== operationRef.current)
          return
        setState({
          ...EMPTY_STATE,
          bindingKey,
          phase: "restoring",
          error: errorMessage(reason),
        })
      })
    return () => controller.abort()
  }, [
    activeAmendmentId,
    bindingKey,
    enabled,
    restoreRevision,
    run?.read_model.status,
    runId,
  ])

  const begin = useCallback(() => {
    if (!canStart || !sourcePayload) return
    keysRef.current = { create: commandKey("create"), apply: "", branch: "" }
    setState({
      ...EMPTY_STATE,
      bindingKey,
      phase: "editing",
      payload: clonePayload(sourcePayload),
    })
  }, [bindingKey, canStart, sourcePayload])

  const change = useCallback((payload: Record<string, unknown>) => {
    setState((currentState) =>
      currentState.phase === "editing" || currentState.phase === "review"
        ? { ...currentState, error: "", payload }
        : currentState,
    )
  }, [])

  const setAuthorNote = useCallback((authorNote: string) => {
    setState((currentState) => ({ ...currentState, authorNote, error: "" }))
  }, [])

  const setScope = useCallback((scope: AmendmentApplyScope) => {
    setState((currentState) => ({ ...currentState, scope }))
  }, [])

  const openReview = useCallback(() => {
    setState((currentState) =>
      currentState.phase === "editing"
        ? { ...currentState, phase: "review", error: "" }
        : currentState,
    )
  }, [])

  const returnToEdit = useCallback(() => {
    keysRef.current.create = commandKey("create")
    keysRef.current.apply = ""
    setState((currentState) => ({
      ...currentState,
      amendment: null,
      impact: null,
      applyReceipt: null,
      phase: "editing",
      error: "",
    }))
  }, [])

  const cancel = useCallback(() => {
    keysRef.current = { create: "", apply: "", branch: "" }
    setState({ ...EMPTY_STATE, bindingKey })
  }, [bindingKey])

  const preview = useCallback(async () => {
    const snapshot = state
    if (snapshot.phase !== "review" || !snapshot.payload || !current || !runId)
      return null
    setState((value) => ({ ...value, phase: "previewing", error: "" }))
    try {
      const result = await createArtifactAmendment(runId, stageId, {
        sourceArtifactRef: current.artifact_ref,
        proposedPayload: snapshot.payload,
        idempotencyKey:
          keysRef.current.create ||
          (keysRef.current.create = commandKey("create")),
        authorNote: snapshot.authorNote,
      })
      setState((value) => ({
        ...value,
        amendment: result.amendment,
        impact: result.impact,
        phase: "impact",
        error: "",
      }))
      return result
    } catch (reason) {
      setState((value) => ({
        ...value,
        phase: "review",
        error: errorMessage(reason),
      }))
      return null
    }
  }, [current, runId, stageId, state])

  const apply = useCallback(async () => {
    const snapshot = state
    if (
      snapshot.phase !== "impact" ||
      !snapshot.amendment ||
      !snapshot.impact ||
      snapshot.impact.blocked_references.length ||
      !runId
    )
      return null
    setState((value) => ({ ...value, phase: "applying", error: "" }))
    try {
      const result = await applyArtifactAmendment(
        runId,
        snapshot.amendment.amendment_id,
        {
          scope: snapshot.scope,
          idempotencyKey:
            keysRef.current.apply ||
            (keysRef.current.apply = commandKey("apply")),
        },
      )
      setState((value) => ({
        ...value,
        applyReceipt: result.receipt,
        phase: "applied",
        error: "",
      }))
      await onSourceRunChanged?.()
      return result
    } catch (reason) {
      setState((value) => ({
        ...value,
        phase: "impact",
        error: errorMessage(reason),
      }))
      return null
    }
  }, [onSourceRunChanged, runId, state])

  const branch = useCallback(async () => {
    const snapshot = state
    const amendmentId = snapshot.amendment?.amendment_id || activeAmendmentId
    if (
      snapshot.phase !== "applied" ||
      !snapshot.applyReceipt ||
      !amendmentId ||
      !runId
    )
      return null
    setState((value) => ({ ...value, phase: "branching", error: "" }))
    try {
      const result = await createArtifactAmendmentBranch(runId, amendmentId, {
        applyReceiptId: snapshot.applyReceipt.receipt_id,
        sourceDomainRevision: snapshot.applyReceipt.domain_revision_after,
        idempotencyKey:
          keysRef.current.branch ||
          (keysRef.current.branch = commandKey("branch")),
      })
      setState((value) => ({
        ...value,
        branchReceipt: result.receipt,
        targetRun: result.target_run,
        phase: "successor",
        error: "",
      }))
      return result
    } catch (reason) {
      setState((value) => ({
        ...value,
        phase: "applied",
        error: errorMessage(reason),
      }))
      return null
    }
  }, [activeAmendmentId, runId, state])

  const retryRestore = useCallback(() => {
    setRestoreRevision((value) => value + 1)
  }, [])

  const hasChanges = useMemo(
    () =>
      Boolean(
        state.payload &&
          sourcePayload &&
          JSON.stringify(state.payload) !== JSON.stringify(sourcePayload),
      ),
    [sourcePayload, state.payload],
  )

  return {
    ...state,
    apply,
    begin,
    branch,
    canStart,
    cancel,
    change,
    hasChanges,
    openReview,
    preview,
    retryRestore,
    returnToEdit,
    setAuthorNote,
    setScope,
  }
}

export type ArtifactAmendmentController = ReturnType<typeof useArtifactAmendment>

let commandSequence = 0

function commandKey(kind: string) {
  commandSequence += 1
  const uuid = globalThis.crypto?.randomUUID?.()
  return `phase32-ui:${kind}:${uuid || `${Date.now()}-${commandSequence}`}`
}

function clonePayload(payload: Record<string, unknown>) {
  return typeof structuredClone === "function"
    ? structuredClone(payload)
    : JSON.parse(JSON.stringify(payload)) as Record<string, unknown>
}

function errorMessage(reason: unknown) {
  return reason instanceof Error ? reason.message : "正式修订请求失败"
}
