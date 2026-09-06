// @vitest-environment happy-dom

import { act } from "react"
import { createRoot } from "react-dom/client"
import { beforeEach, describe, expect, it, vi } from "vitest"
import type { StoryBibleSection } from "../../contracts/storyBible"
import StoryBiblePage from "./StoryBiblePage"

const mocks = vi.hoisted(() => ({
  setRoute: vi.fn(),
  useStoryBible: vi.fn(),
}))

vi.mock("../../layout/useLoadingPresence", () => ({
  useLoadingPresence: () => ({ exiting: false, visible: false }),
}))

vi.mock("../../state/PipelineAppProvider", () => ({
  useApp: () => ({
    activeProject: {
      id: "project-story-bible",
      routeLabel: "长篇小说",
      title: "潮汐档案",
    },
    activeRun: {
      definition: {
        route_contract: { creation_route_id: "long_novel" },
        run_id: "run-story-bible",
      },
      read_model: { updated_at: "2026-08-25T12:00:00+08:00" },
    },
    runLoading: false,
    setRoute: mocks.setRoute,
  }),
}))

vi.mock("../../state/useStoryBible", () => ({
  useStoryBible: (...args: unknown[]) => mocks.useStoryBible(...args),
}))
;(globalThis as Record<string, unknown>).IS_REACT_ACT_ENVIRONMENT = true

describe("StoryBiblePage", () => {
  beforeEach(() => {
    vi.clearAllMocks()
    window.history.replaceState(
      null,
      "",
      "/bible/overview?project=project-story-bible",
    )
    mocks.useStoryBible.mockImplementation(
      (_runId: string, section: StoryBibleSection) => pageState(section),
    )
  })

  it("switches route-aware tabs and opens the committed source stage", async () => {
    const container = document.createElement("div")
    const root = createRoot(container)
    await act(async () => root.render(<StoryBiblePage />))

    const structureTab = Array.from(container.querySelectorAll("button")).find(
      (button) => button.textContent?.includes("全书架构"),
    )!
    act(() => structureTab.click())

    expect(window.location.pathname).toBe("/bible/structure")
    expect(window.location.search).toBe("?project=project-story-bible")
    expect(structureTab.getAttribute("aria-current")).toBe("page")
    expect(container.textContent).toContain("第一卷证据封锁")

    act(() =>
      container
        .querySelector<HTMLButtonElement>(".story-bible-source")
        ?.click(),
    )
    expect(mocks.setRoute).toHaveBeenCalledWith("book_architecture")

    act(() => root.unmount())
  })

  it("keeps the active category visible inside a narrow horizontal tab list", async () => {
    const container = document.createElement("div")
    const root = createRoot(container)
    await act(async () => root.render(<StoryBiblePage />))

    const tabList = container.querySelector<HTMLElement>(".story-bible-tabs")!
    const continuityTab = Array.from(tabList.querySelectorAll("button")).find(
      (button) => button.textContent?.includes("连续性"),
    )!
    Object.defineProperty(tabList, "clientWidth", {
      configurable: true,
      value: 200,
    })
    Object.defineProperty(continuityTab, "offsetLeft", {
      configurable: true,
      value: 260,
    })
    Object.defineProperty(continuityTab, "offsetWidth", {
      configurable: true,
      value: 80,
    })

    act(() => continuityTab.click())

    expect(window.location.pathname).toBe("/bible/continuity")
    expect(tabList.scrollLeft).toBe(140)

    act(() => root.unmount())
  })

  it("projects committed Canon and Wiki status without the retired placeholder", async () => {
    window.history.replaceState(
      null,
      "",
      "/bible/continuity?project=project-story-bible",
    )
    mocks.useStoryBible.mockImplementation(
      (_runId: string, section: StoryBibleSection) => ({
        ...pageState(section),
        summary: {
          ...pageState(section).summary,
          formal_fact_count: 1,
          formal_writeback_status: "committed",
        },
      }),
    )
    const container = document.createElement("div")
    const root = createRoot(container)
    await act(async () => root.render(<StoryBiblePage />))

    expect(container.textContent).toContain("已核验 1 条正式事实")
    expect(container.textContent).toContain("Canon")
    expect(container.textContent).not.toContain("将在正式修订合同完成后接入")

    act(() => root.unmount())
  })
})

function pageState(section: StoryBibleSection) {
  return {
    error: "",
    items: section === "structure" ? [structureEntry()] : [overviewEntry()],
    loadMore: vi.fn(),
    nextCursor: null,
    refreshing: false,
    status: "ready",
    summary: {
      title: "潮汐档案",
      route_label: "长篇小说",
      run_status: "running",
      active_stage_id: "book_architecture",
      updated_at: "2026-08-25T12:00:00+08:00",
      projection_revision: "b".repeat(64),
      available_sections: [
        "overview",
        "cast",
        "structure",
        "units",
        "continuity",
      ],
      source_artifact_count: 2,
      character_count: 0,
      relationship_count: 0,
      structure_count: 1,
      accepted_unit_count: 0,
      continuity_count: 0,
      tracked_promise_count: 0,
      open_question_count: 0,
      formal_fact_count: 0,
      formal_writeback_status: "not_started",
    },
    total: 1,
  }
}

function overviewEntry() {
  return {
    ...entryBase(),
    entry_ref: "brief-premise",
    kind: "brief_field" as const,
    title: "故事前提",
    body: "一座港城的公开档案正在被系统性改写。",
    source: {
      ...entryBase().source,
      stage_id: "brief",
      source_path: "brief.premise",
    },
  }
}

function structureEntry() {
  return {
    ...entryBase(),
    entry_ref: "volume-1",
    kind: "volume" as const,
    title: "第一卷证据封锁",
    body: "主角必须在证词失效前建立公开证据链。",
    source: {
      ...entryBase().source,
      stage_id: "book_architecture",
      source_path: "book.parts[0].volumes[0]",
    },
  }
}

function entryBase() {
  return {
    entry_ref: "entry",
    kind: "part" as const,
    title: "结构",
    body: "结构正文",
    detail: "直接来自已提交架构。",
    status: "committed" as const,
    ordinal: 1,
    parent_ref: "",
    unit_ref: "",
    subject_refs: [],
    promise_refs: [],
    tags: [],
    authority: "committed_artifact" as const,
    confidence: "direct" as const,
    source: {
      stage_id: "book_architecture",
      artifact_kind: "book_architecture",
      artifact_ref: `p32-book_architecture-committed-${"c".repeat(64)}`,
      payload_digest: "c".repeat(64),
      source_path: "book",
      committed_at: "2026-08-25T12:00:00+08:00",
    },
  }
}
