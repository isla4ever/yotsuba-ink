// @vitest-environment happy-dom

import { act } from "react"
import { createRoot } from "react-dom/client"
import { beforeEach, describe, expect, it, vi } from "vitest"
import { StageProgressTrace } from "./StageProgressTrace"

const mocks = vi.hoisted(() => ({
  statuses: {
    brief: "committed",
    spine: "committed",
    cast: "committed",
    volumes: "committed",
    detail: "warning",
    text: "pending",
    cover: "pending",
    export: "pending",
  },
}))

vi.mock("../state/PipelineAppProvider", () => ({
  useApp: () => ({
    activeProject: { stageStatuses: mocks.statuses },
    activeRun: {
      read_model: {
        active_stage_id: "detail",
        updated_at: "2026-08-21T12:00:00Z",
      },
    },
  }),
}))

vi.mock("../lib/runPresentation", () => ({
  runStageStatuses: () => mocks.statuses,
}))

;(globalThis as Record<string, unknown>).IS_REACT_ACT_ENVIRONMENT = true

describe("StageProgressTrace", () => {
  beforeEach(() => vi.clearAllMocks())

  it("separates the browsed stage from the live run stage", () => {
    const container = document.createElement("div")
    const root = createRoot(container)
    act(() => root.render(<StageProgressTrace route="volumes" setRoute={vi.fn()} />))

    expect(
      container.querySelector('button[aria-current="step"]')?.textContent,
    ).toContain("卷册")
    expect(container.textContent).toContain("待确认")
    expect(container.querySelector(".stage-progress-live-beat")).not.toBeNull()
    expect(
      container.querySelector(".stage-progress-complete")?.getAttribute("d"),
    ).toContain("L")

    act(() => root.unmount())
  })

  it("keeps every stage directly navigable from the compact trace", () => {
    const container = document.createElement("div")
    const root = createRoot(container)
    const setRoute = vi.fn()
    act(() => root.render(<StageProgressTrace route="volumes" setRoute={setRoute} />))

    act(() =>
      container
        .querySelector<HTMLButtonElement>('button[aria-label="5·细纲"]')
        ?.click(),
    )
    expect(setRoute).toHaveBeenCalledWith("detail")

    act(() => root.unmount())
  })
})
