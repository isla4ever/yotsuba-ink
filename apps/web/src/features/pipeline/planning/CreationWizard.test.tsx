// @vitest-environment happy-dom

import { act } from "react"
import { createRoot, type Root } from "react-dom/client"
import { beforeEach, describe, expect, it, vi } from "vitest"
import type {
  CreationIntentDraft,
  CreationWorkflowCatalogItem,
} from "../contracts/creationWizard"
import CreationWizard from "./CreationWizard"

const mocks = vi.hoisted(() => ({
  creationWizardDraft: {
    creativeIntent:
      "一名修复师收到来自未来的失踪报告，并必须决定是否改写家人的旧案。",
    creationKind: "novel" as const,
    novelLengthClass: "short_novel" as const,
    requestedTarget: 20_000,
  } as CreationIntentDraft | null,
  createProject: vi.fn(),
  openProject: vi.fn(),
  selectedTemplateId: "custom-short-a" as string | null,
  setCreationWizardDraft: vi.fn(),
  setMode: vi.fn(),
  setRoute: vi.fn(),
  workflows: [] as CreationWorkflowCatalogItem[],
}))

vi.mock("../state/PipelineAppProvider", () => ({
  useApp: () => ({
    creationWizardDraft: mocks.creationWizardDraft,
    openProject: mocks.openProject,
    selectedTemplateId: mocks.selectedTemplateId,
    setCreationWizardDraft: mocks.setCreationWizardDraft,
    setMode: mocks.setMode,
    setRoute: mocks.setRoute,
    setSelectedTemplateId: (id: string | null) => {
      mocks.selectedTemplateId = id
    },
  }),
}))

vi.mock("../state/useWorkflowTemplates", () => ({
  useWorkflowTemplates: () => ({
    error: "",
    loading: false,
    refresh: vi.fn(),
    workflows: mocks.workflows,
  }),
}))

vi.mock("../layout/useLoadingPresence", () => ({
  useLoadingPresence: () => ({ exiting: false, visible: false }),
}))

vi.mock("../services/projectApi", () => ({
  createProject: mocks.createProject,
}))

vi.mock("../lib/projectPresentation", () => ({
  projectPresentation: () => ({ id: "phase32-project" }),
}))
;(globalThis as Record<string, unknown>).IS_REACT_ACT_ENVIRONMENT = true

describe("CreationWizard idempotency boundary", () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mocks.creationWizardDraft = {
      creativeIntent:
        "一名修复师收到来自未来的失踪报告，并必须决定是否改写家人的旧案。",
      creationKind: "novel",
      novelLengthClass: "short_novel",
      requestedTarget: 20_000,
    }
    mocks.selectedTemplateId = "custom-short-a"
    mocks.workflows = [
      workflow("custom-short-a", "短篇流水线 A"),
      workflow("custom-short-b", "短篇流水线 B"),
    ]
  })

  it("keeps the key for an identical retry", async () => {
    mocks.createProject
      .mockRejectedValueOnce(new Error("temporary failure"))
      .mockResolvedValueOnce({ id: "phase32-project" })
    const view = renderWizard()

    await clickCreate(view.container)
    await clickCreate(view.container)

    expect(mocks.createProject).toHaveBeenCalledTimes(2)
    expect(mocks.createProject.mock.calls[1][0].idempotencyKey).toBe(
      mocks.createProject.mock.calls[0][0].idempotencyKey,
    )
    view.unmount()
  })

  it("rotates the key after selecting another workflow", async () => {
    mocks.createProject
      .mockRejectedValueOnce(new Error("temporary failure"))
      .mockResolvedValueOnce({ id: "phase32-project" })
    const view = renderWizard()

    await clickCreate(view.container)
    const secondWorkflow = Array.from(
      view.container.querySelectorAll<HTMLButtonElement>('[role="radio"]'),
    ).find((button) => button.textContent?.includes("短篇流水线 B"))
    act(() => secondWorkflow?.click())
    act(() => view.root.render(<CreationWizard />))
    await clickCreate(view.container)

    expect(mocks.createProject).toHaveBeenCalledTimes(2)
    expect(mocks.createProject.mock.calls[1][0].workflowId).toBe(
      "custom-short-b",
    )
    expect(mocks.createProject.mock.calls[1][0].idempotencyKey).not.toBe(
      mocks.createProject.mock.calls[0][0].idempotencyKey,
    )
    view.unmount()
  })

  it("renders the route-owned stage chain instead of legacy workflow nodes", () => {
    const view = renderWizard()
    const content = view.container.textContent ?? ""

    expect(content).toContain("故事地图")
    expect(content).toContain("章节与段落计划")
    expect(content.indexOf("故事地图")).toBeLessThan(
      content.indexOf("人物圣经"),
    )
    expect(content).not.toContain("故事脊柱")
    expect(content).not.toContain("8 阶段生产合同")
    view.unmount()
  })

  it("returns a route shortcut without an intent to the required first step", () => {
    mocks.creationWizardDraft = null

    const view = renderWizard()
    const content = view.container.textContent ?? ""

    expect(content).toContain("先确定这次要交付什么")
    expect(content).not.toContain("创建作品并进入 Brief")
    view.unmount()
  })
})

function renderWizard(): {
  container: HTMLDivElement
  root: Root
  unmount: () => void
} {
  const container = document.createElement("div")
  const root = createRoot(container)
  act(() => root.render(<CreationWizard />))
  return {
    container,
    root,
    unmount: () => act(() => root.unmount()),
  }
}

async function clickCreate(container: HTMLDivElement) {
  const button = Array.from(
    container.querySelectorAll<HTMLButtonElement>("button"),
  ).find((item) => item.textContent?.includes("创建作品并进入 Brief"))
  await act(async () => {
    button?.click()
  })
}

function workflow(id: string, name: string): CreationWorkflowCatalogItem {
  return {
    id,
    routeId: "short_novel",
    name,
    source: "custom",
    revision: "r1",
    workflowDigest: "a".repeat(64),
    summary: `${name}测试配置`,
    available: true,
    deliverableKind: "short_novel",
    stages: [],
    capabilities: [],
    exportProfiles: ["markdown"],
    scalePolicy: {
      unit: "characters",
      minimum: 2_000,
      recommendedFloor: 10_000,
      recommended: 20_000,
      recommendedCeiling: 30_000,
      maximum: 130_000,
      rationale: "测试规模",
    },
    reviewPolicy: {
      policyId: "review.short_novel.default",
      revision: "r1",
      checkpointPolicy: "route_defined",
      warningPolicy: "visible_non_blocking",
      contractCorrectionLimit: 1,
      directedRedraftLimitByStage: {},
      autoContinueStages: [],
      mandatoryDecisionStages: [],
    },
  }
}
