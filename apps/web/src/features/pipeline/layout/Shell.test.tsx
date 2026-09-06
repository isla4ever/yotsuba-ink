// @vitest-environment happy-dom

import { act } from "react"
import { createRoot } from "react-dom/client"
import { beforeEach, describe, expect, it, vi } from "vitest"
import Shell from "./Shell"

const mocks = vi.hoisted(() => ({
  setRoute: vi.fn(),
  state: {} as Record<string, unknown>,
}))

vi.mock("../state/PipelineAppProvider", () => ({
  useApp: () => mocks.state,
}))

vi.mock("../running/collaboration/AuthorCollaborationDock", () => ({
  AuthorCollaborationDock: () => (
    <aside aria-label="作者协作 Dock">Phase 32 collaboration</aside>
  ),
}))
;(globalThis as Record<string, unknown>).IS_REACT_ACT_ENVIRONMENT = true

describe("Phase 32 project Shell", () => {
  beforeEach(() => {
    vi.clearAllMocks()
    Object.assign(mocks.state, appState("brief", false, "running"))
  })

  it("keeps the formal run monitor entry visible", () => {
    const container = document.createElement("div")
    const root = createRoot(container)
    act(() =>
      root.render(
        <Shell>
          <div>stage</div>
        </Shell>,
      ),
    )

    const monitorButtons = Array.from(
      container.querySelectorAll<HTMLButtonElement>("button"),
    ).filter((button) => button.textContent?.includes("监控"))
    expect(monitorButtons.length).toBeGreaterThan(0)

    act(() => monitorButtons[0].click())
    expect(mocks.setRoute).toHaveBeenCalledWith("run-monitor")

    act(() => root.unmount())
  })

  it("shows collaboration only for an unlocked manifest capability", () => {
    const container = document.createElement("div")
    const root = createRoot(container)
    act(() =>
      root.render(
        <Shell>
          <div>stage</div>
        </Shell>,
      ),
    )
    expect(
      container.querySelector('button[aria-label="打开作者协作"]'),
    ).toBeNull()

    Object.assign(mocks.state, appState("story_map", true, "locked"))
    act(() =>
      root.render(
        <Shell>
          <div>stage</div>
        </Shell>,
      ),
    )
    expect(
      container.querySelector('button[aria-label="打开作者协作"]'),
    ).toBeNull()

    Object.assign(mocks.state, appState("story_map", true, "awaiting_decision"))
    act(() =>
      root.render(
        <Shell>
          <div>stage</div>
        </Shell>,
      ),
    )
    expect(
      container.querySelectorAll('button[aria-label="打开作者协作"]'),
    ).toHaveLength(2)

    act(() => root.unmount())
  })

  it("hides the project sidebar while the dock is open and closes on route change", async () => {
    Object.assign(mocks.state, appState("story_map", true, "awaiting_decision"))
    const container = document.createElement("div")
    const root = createRoot(container)
    act(() =>
      root.render(
        <Shell>
          <div>stage</div>
        </Shell>,
      ),
    )
    expect(container.textContent).toContain("返回创作台")

    const trigger = container.querySelector<HTMLButtonElement>(
      'button[aria-label="打开作者协作"]',
    )
    await act(async () => {
      trigger?.click()
      await Promise.resolve()
    })
    expect(
      container.querySelector('[aria-label="作者协作 Dock"]'),
    ).not.toBeNull()
    expect(container.textContent).not.toContain("返回创作台")

    Object.assign(mocks.state, appState("cover", false, "running"))
    act(() =>
      root.render(
        <Shell>
          <div>cover</div>
        </Shell>,
      ),
    )
    expect(container.querySelector('[aria-label="作者协作 Dock"]')).toBeNull()

    act(() => root.unmount())
  })
})

function appState(
  route: string,
  collaborationEnabled: boolean,
  stageStatus: string,
) {
  const stage = {
    artifact_kind: route === "cover" ? "cover" : "story_map",
    collaboration_enabled: collaborationEnabled,
    context_policy_ref: "phase32.context.v1",
    decision_policy_ref: "phase32.decision.v1",
    downstream_stage_ids: [],
    label:
      route === "brief" ? "小说立项" : route === "cover" ? "封面" : "故事地图",
    ordinal: 0,
    provider_task_kind: route === "cover" ? null : route,
    stage_id: route,
    unitization: "aggregate",
    upstream_stage_ids: [],
    workbench_kind: route,
  }
  return {
    activeProject: {
      architectureVersion: "phase32-routes-v1",
      id: "project-1",
      latestRunId: "run-1",
      routeLabel: "短中篇小说",
      stageManifest: [{ id: route, label: stage.label, ordinal: 0 }],
      stageStatuses: { [route]: "active" },
      subtitle: "一次封闭空间里的短篇故事",
      title: "待定标题",
    },
    activeRun: {
      definition: { run_id: "run-1" },
      read_model: {
        active_stage_id: route,
        stage_manifest: [stage],
        stage_status: { [route]: stageStatus },
        status: "running",
        updated_at: "2026-08-23T12:00:00+08:00",
      },
    },
    closeProject: vi.fn(),
    mobileDrawerOpen: false,
    projectOpen: true,
    route,
    runConnection: "live",
    runError: "",
    runLoading: false,
    setCmdOpen: vi.fn(),
    setMobileDrawerOpen: vi.fn(),
    setRoute: mocks.setRoute,
    sidebarCollapsed: false,
    theme: "dark",
    toggleSidebar: vi.fn(),
    toggleTheme: vi.fn(),
  }
}
