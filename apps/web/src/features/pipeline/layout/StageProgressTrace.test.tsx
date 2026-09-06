// @vitest-environment happy-dom

import { act } from "react"
import { createRoot } from "react-dom/client"
import { beforeEach, describe, expect, it, vi } from "vitest"
import { StageProgressTrace } from "./StageProgressTrace"

const mocks = vi.hoisted(() => ({
  runStatus: "awaiting_decision",
  statuses: {
    brief: "committed",
    story_map: "committed",
    cast: "committed",
    section_plan: "warning",
    text: "pending",
    cover: "pending",
    export: "pending",
  },
  stages: [
    { id: "brief", label: "小说立项", ordinal: 0 },
    { id: "story_map", label: "故事地图", ordinal: 1 },
    { id: "cast", label: "人物圣经", ordinal: 2 },
    { id: "section_plan", label: "章节规划", ordinal: 3 },
    { id: "text", label: "小说正文", ordinal: 4 },
    { id: "cover", label: "封面", ordinal: 5 },
    { id: "export", label: "交付", ordinal: 6 },
  ],
}))

vi.mock("../state/PipelineAppProvider", () => ({
  useApp: () => ({
    activeProject: {
      stageManifest: mocks.stages,
      stageStatuses: mocks.statuses,
    },
    activeRun: {
      read_model: {
        active_stage_id: "section_plan",
        status: mocks.runStatus,
        stage_manifest: mocks.stages.map((stage) => ({
          stage_id: stage.id,
          label: stage.label,
          ordinal: stage.ordinal,
        })),
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
  beforeEach(() => {
    vi.clearAllMocks()
    mocks.runStatus = "awaiting_decision"
  })

  it("separates the browsed stage from the live run stage", () => {
    const container = document.createElement("div")
    const root = createRoot(container)
    act(() =>
      root.render(<StageProgressTrace route="story_map" setRoute={vi.fn()} />),
    )

    expect(
      container.querySelector('button[aria-current="step"]')?.textContent,
    ).toContain("故事地图")
    expect(container.textContent).toContain("待确认")
    expect(container.querySelector(".stage-progress-live-beat")).toBeNull()
    expect(
      container.querySelector(".stage-progress-complete")?.getAttribute("d"),
    ).toContain("L")

    act(() => root.unmount())
  })

  it("labels the available first stage as waiting before execution starts", () => {
    const statuses = mocks.statuses
    mocks.runStatus = "created"
    mocks.statuses = {
      brief: "active",
      story_map: "pending",
      cast: "pending",
      section_plan: "pending",
      text: "pending",
      cover: "pending",
      export: "pending",
    }
    const container = document.createElement("div")
    const root = createRoot(container)

    act(() =>
      root.render(<StageProgressTrace route="brief" setRoute={vi.fn()} />),
    )

    expect(container.textContent).toContain("待启动")
    expect(container.querySelector(".stage-progress-live-beat")).toBeNull()

    act(() => root.unmount())
    mocks.statuses = statuses
  })

  it("navigates available stages and keeps locked stages disabled", () => {
    const container = document.createElement("div")
    const root = createRoot(container)
    const setRoute = vi.fn()
    act(() =>
      root.render(<StageProgressTrace route="story_map" setRoute={setRoute} />),
    )

    act(() =>
      container
        .querySelector<HTMLButtonElement>('button[aria-label="4·章节规划"]')
        ?.click(),
    )
    expect(setRoute).toHaveBeenCalledWith("section_plan")
    expect(
      container.querySelector<HTMLButtonElement>(
        'button[aria-label="5·小说正文"]',
      )?.disabled,
    ).toBe(true)

    act(() => root.unmount())
  })

  it("keeps the initial empty projection at a finite zero-width cursor", () => {
    const stages = mocks.stages
    mocks.stages = []
    const container = document.createElement("div")
    const root = createRoot(container)

    act(() =>
      root.render(<StageProgressTrace route="brief" setRoute={vi.fn()} />),
    )

    expect(
      container.querySelector("clipPath rect")?.getAttribute("width"),
    ).toBe("0%")

    act(() => root.unmount())
    mocks.stages = stages
  })
})
