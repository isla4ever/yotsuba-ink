// @vitest-environment happy-dom

import { act, useEffect } from "react"
import { createRoot } from "react-dom/client"
import { beforeEach, describe, expect, it, vi } from "vitest"
import { ScriptDeliveryApiError } from "../services/scriptDeliveryApi"
import { usePhase32ScriptDelivery } from "./usePhase32ScriptDelivery"

const mocks = vi.hoisted(() => ({
  getScriptDelivery: vi.fn(),
  getCurrentArtifact: vi.fn(),
}))

vi.mock("../services/scriptDeliveryApi", async () => {
  const actual =
    await vi.importActual<typeof import("../services/scriptDeliveryApi")>(
      "../services/scriptDeliveryApi",
    )
  return { ...actual, getScriptDelivery: mocks.getScriptDelivery }
})

vi.mock("../services/runApi", () => ({
  getPhase32CurrentArtifact: mocks.getCurrentArtifact,
}))
;(globalThis as Record<string, unknown>).IS_REACT_ACT_ENVIRONMENT = true

type HookState = ReturnType<typeof usePhase32ScriptDelivery>

describe("usePhase32ScriptDelivery", () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it("keeps image-deferred metadata when export artifact is absent", async () => {
    mocks.getScriptDelivery.mockRejectedValue(
      new ScriptDeliveryApiError(
        "图片验收尚未启用，当前 Run 仅完成 CoverBrief，暂不可导出剧本。",
        409,
        {
          code: "image_deferred",
          artifactType: "script_delivery",
          dependencyStatus: "deferred",
          deferredReason: "image_acceptance_not_in_current_wave",
          sourceArtifactRefs: ["p32-cover-ref"],
        },
      ),
    )
    let latest: HookState | null = null
    const container = document.createElement("div")
    const root = createRoot(container)

    await act(async () => {
      root.render(<Probe onValue={(value) => (latest = value)} />)
    })
    await vi.waitFor(() => expect(requireValue(latest).loading).toBe(false))

    expect(requireValue(latest)).toMatchObject({
      errorCode: "image_deferred",
      dependencyStatus: "deferred",
      deferredReason: "image_acceptance_not_in_current_wave",
      sourceArtifactRefs: ["p32-cover-ref"],
    })
    expect(mocks.getCurrentArtifact).not.toHaveBeenCalled()
    act(() => root.unmount())
  })
})

function requireValue(value: HookState | null): HookState {
  if (value === null) throw new Error("Probe did not publish hook state")
  return value
}

function Probe({ onValue }: { onValue: (value: HookState) => void }) {
  const value = usePhase32ScriptDelivery("run-script-1", "revision-1")
  useEffect(() => {
    onValue(value)
  }, [onValue, value])
  return null
}
