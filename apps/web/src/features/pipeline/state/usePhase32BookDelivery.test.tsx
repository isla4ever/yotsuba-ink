// @vitest-environment happy-dom

import { act, useEffect } from "react"
import { createRoot } from "react-dom/client"
import { beforeEach, describe, expect, it, vi } from "vitest"
import { BookDeliveryApiError } from "../services/bookDeliveryApi"
import { usePhase32BookDelivery } from "./usePhase32BookDelivery"

const mocks = vi.hoisted(() => ({
  getBookDelivery: vi.fn(),
  getCurrentArtifact: vi.fn(),
}))

vi.mock("../services/bookDeliveryApi", async () => {
  const actual =
    await vi.importActual<typeof import("../services/bookDeliveryApi")>(
      "../services/bookDeliveryApi",
    )
  return { ...actual, getBookDelivery: mocks.getBookDelivery }
})

vi.mock("../services/runApi", () => ({
  getPhase32CurrentArtifact: mocks.getCurrentArtifact,
}))
;(globalThis as Record<string, unknown>).IS_REACT_ACT_ENVIRONMENT = true

type HookState = ReturnType<typeof usePhase32BookDelivery>

describe("usePhase32BookDelivery", () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it("keeps image-deferred metadata when export artifact is absent", async () => {
    mocks.getBookDelivery.mockRejectedValue(
      new BookDeliveryApiError(
        "图片验收尚未启用，当前 Run 仅完成 CoverBrief，暂不可导出成书。",
        409,
        {
          code: "image_deferred",
          artifactType: "book_delivery",
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
  const value = usePhase32BookDelivery("run-book-1", "revision-1")
  useEffect(() => {
    onValue(value)
  }, [onValue, value])
  return null
}
