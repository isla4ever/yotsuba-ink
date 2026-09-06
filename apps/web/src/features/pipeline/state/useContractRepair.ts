import { useCallback, useEffect, useMemo, useRef, useState } from "react"
import type { Phase32ContractQuarantine } from "../contracts/contractRepair"
import type { Phase32RunEnvelope } from "../contracts/run"
import {
  getCurrentContractQuarantine,
  repairContractCandidate,
} from "../services/contractRepairApi"

export type ContractRepairPhase = "loading" | "unavailable" | "ready" | "editing" | "submitting" | "restored"

type State = {
  phase: ContractRepairPhase
  quarantine: Phase32ContractQuarantine | null
  payload: Record<string, unknown> | null
  error: string
}

const EMPTY_STATE: State = {
  phase: "loading",
  quarantine: null,
  payload: null,
  error: "",
}

export function useContractRepair({
  enabled,
  onRestored,
  run,
}: {
  enabled: boolean
  onRestored: (run: Phase32RunEnvelope) => Promise<unknown> | unknown
  run: Phase32RunEnvelope
}) {
  const [state, setState] = useState<State>(EMPTY_STATE)
  const operationRef = useRef(0)
  const repairIdRef = useRef("")
  const runId = run.definition.run_id
  const authorityKey = `${runId}\0${run.read_model.updated_at}`

  useEffect(() => {
    const operation = ++operationRef.current
    repairIdRef.current = ""
    if (!enabled) {
      setState({ ...EMPTY_STATE, phase: "unavailable" })
      return undefined
    }
    const controller = new AbortController()
    setState(EMPTY_STATE)
    void getCurrentContractQuarantine(runId, controller.signal)
      .then((quarantine) => {
        if (controller.signal.aborted || operation !== operationRef.current)
          return
        setState({
          phase: quarantine.eligible ? "ready" : "unavailable",
          quarantine,
          payload: null,
          error: "",
        })
      })
      .catch((reason) => {
        if (controller.signal.aborted || operation !== operationRef.current)
          return
        setState({
          phase: "unavailable",
          quarantine: null,
          payload: null,
          error: errorMessage(reason),
        })
      })
    return () => controller.abort()
  }, [authorityKey, enabled, runId])

  const begin = useCallback(() => {
    setState((current) => {
      if (current.phase !== "ready" || !current.quarantine?.eligible)
        return current
      repairIdRef.current ||= repairId()
      return {
        ...current,
        phase: "editing",
        payload: clonePayload(current.quarantine.source_payload),
        error: "",
      }
    })
  }, [])

  const change = useCallback((payload: Record<string, unknown>) => {
    setState((current) =>
      current.phase === "editing"
        ? { ...current, payload, error: "" }
        : current,
    )
  }, [])

  const cancel = useCallback(() => {
    setState((current) =>
      current.quarantine
        ? {
            ...current,
            phase: current.quarantine.eligible ? "ready" : "unavailable",
            payload: null,
            error: "",
          }
        : current,
    )
  }, [])

  const submit = useCallback(async () => {
    const snapshot = state
    if (
      snapshot.phase !== "editing" ||
      !snapshot.quarantine?.eligible ||
      !snapshot.payload
    )
      return null
    setState((current) => ({ ...current, phase: "submitting", error: "" }))
    try {
      repairIdRef.current ||= repairId()
      const result = await repairContractCandidate(runId, {
        repairId: repairIdRef.current,
        quarantine: snapshot.quarantine,
        payload: snapshot.payload,
      })
      const before = run.read_model.provider_usage.provider_operations
      const after = result.run.read_model.provider_usage.provider_operations
      if (after !== before)
        throw new Error(
          `合同修复不得创建 Provider 调用：修复前 ${before}，修复后 ${after}`,
        )
      setState((current) => ({ ...current, phase: "restored", error: "" }))
      await onRestored(result.run)
      return result
    } catch (reason) {
      setState((current) => ({
        ...current,
        phase: "editing",
        error: errorMessage(reason),
      }))
      return null
    }
  }, [onRestored, run, runId, state])

  const hasChanges = useMemo(
    () =>
      Boolean(
        state.payload &&
          state.quarantine &&
          JSON.stringify(state.payload) !==
            JSON.stringify(state.quarantine.source_payload),
      ),
    [state.payload, state.quarantine],
  )

  return { ...state, begin, cancel, change, hasChanges, submit }
}

export type ContractRepairController = ReturnType<typeof useContractRepair>

let repairSequence = 0

function repairId() {
  repairSequence += 1
  const uuid = globalThis.crypto?.randomUUID?.()
  return `phase32-ui:contract-repair:${uuid || `${Date.now()}-${repairSequence}`}`
}

function clonePayload(payload: Record<string, unknown>) {
  return typeof structuredClone === "function"
    ? structuredClone(payload)
    : JSON.parse(JSON.stringify(payload)) as Record<string, unknown>
}

function errorMessage(reason: unknown) {
  return reason instanceof Error ? reason.message : "隔离稿修复请求失败"
}
