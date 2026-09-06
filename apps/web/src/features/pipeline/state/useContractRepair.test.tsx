// @vitest-environment happy-dom

import { act } from "react"
import { createRoot } from "react-dom/client"
import { beforeEach, describe, expect, it, vi } from "vitest"
import type { Phase32RunEnvelope } from "../contracts/run"
import {
  type ContractRepairController,
  useContractRepair,
} from "./useContractRepair"

const api = vi.hoisted(() => ({
  get: vi.fn(),
  repair: vi.fn(),
}))

vi.mock("../services/contractRepairApi", () => ({
  getCurrentContractQuarantine: api.get,
  repairContractCandidate: api.repair,
}))
;(globalThis as Record<string, unknown>).IS_REACT_ACT_ENVIRONMENT = true

describe("useContractRepair", () => {
  beforeEach(() => vi.clearAllMocks())

  it("keeps one source-bound repair id and verifies zero Provider operations", async () => {
    const run = failedRun(9)
    const restored = restoredRun(9)
    const quarantine = quarantineFixture()
    const onRestored = vi.fn()
    api.get.mockResolvedValue(quarantine)
    api.repair.mockResolvedValue({
      reused: false,
      repair: { candidate_ref: "candidate-repaired" },
      run: restored,
      decision: restored.read_model.pending_decisions[0],
    })
    const harness = renderHook(run, onRestored)

    await eventually(() => harness.value.phase === "ready")
    act(() => harness.value.begin())
    expect(harness.value.phase).toBe("editing")
    act(() => harness.value.change({ windows: [{ fixed: true }] }))
    expect(harness.value.hasChanges).toBe(true)
    await act(async () => {
      await harness.value.submit()
    })

    expect(harness.value.phase).toBe("restored")
    expect(onRestored).toHaveBeenCalledWith(restored)
    expect(api.repair).toHaveBeenCalledWith(
      "contract-run",
      expect.objectContaining({
        repairId: expect.stringContaining("phase32-ui:contract-repair:"),
        quarantine,
        payload: { windows: [{ fixed: true }] },
      }),
    )
    harness.unmount()
  })

  it("keeps a Provider-count violation visible and does not report restoration", async () => {
    const run = failedRun(9)
    const quarantine = quarantineFixture()
    const onRestored = vi.fn()
    api.get.mockResolvedValue(quarantine)
    api.repair.mockResolvedValue({
      run: restoredRun(10),
      decision: {},
      repair: {},
      reused: false,
    })
    const harness = renderHook(run, onRestored)

    await eventually(() => harness.value.phase === "ready")
    act(() => harness.value.begin())
    act(() => harness.value.change({ windows: [{ fixed: true }] }))
    await act(async () => {
      await harness.value.submit()
    })

    expect(harness.value.phase).toBe("editing")
    expect(harness.value.error).toContain("修复前 9，修复后 10")
    expect(onRestored).not.toHaveBeenCalled()
    harness.unmount()
  })
})

function renderHook(
  run: Phase32RunEnvelope,
  onRestored: (run: Phase32RunEnvelope) => void,
) {
  const container = document.createElement("div")
  const root = createRoot(container)
  let value: ContractRepairController = null as never

  function Probe() {
    value = useContractRepair({ enabled: true, onRestored, run })
    return null
  }

  act(() => root.render(<Probe />))
  return {
    get value() {
      return value
    },
    unmount() {
      act(() => root.unmount())
    },
  }
}

async function eventually(predicate: () => boolean) {
  for (let attempt = 0; attempt < 20; attempt += 1) {
    await act(async () => Promise.resolve())
    if (predicate()) return
  }
  throw new Error("condition did not settle")
}

function quarantineFixture() {
  return {
    run_id: "contract-run",
    creation_route_id: "long_novel" as const,
    stage_id: "rolling_detail",
    definition_digest: "a".repeat(64),
    domain_revision: 7,
    provider_receipt_ref: `p32-provider-operation-${"b".repeat(64)}`,
    provider_request_signature: "c".repeat(64),
    source_payload_digest: "d".repeat(64),
    source_payload: { windows: [{ fixed: false }] },
    eligible: true,
    findings: [
      {
        code: "stage_reference_contract_invalid",
        message: "chapter-01 人物范围无效",
      },
    ],
  }
}

function failedRun(providerOperations: number) {
  return {
    definition: { run_id: "contract-run" },
    read_model: {
      updated_at: "2026-09-06T00:00:00Z",
      provider_usage: { provider_operations: providerOperations },
    },
  } as unknown as Phase32RunEnvelope
}

function restoredRun(providerOperations: number) {
  return {
    definition: { run_id: "contract-run" },
    read_model: {
      provider_usage: { provider_operations: providerOperations },
      pending_decisions: [{ decision_id: "decision-repaired" }],
    },
  } as unknown as Phase32RunEnvelope
}
