// @vitest-environment happy-dom

import { act } from "react"
import { createRoot } from "react-dom/client"
import { beforeEach, describe, expect, it, vi } from "vitest"
import type {
  CreationRouteId,
  CreationWorkflowCatalogItem,
} from "@/features/pipeline/contracts/creationWizard"
import WorkflowTemplatesPage from "./WorkflowTemplatesPage"

const mocks = vi.hoisted(() => ({
  refresh: vi.fn(),
  workflows: [] as CreationWorkflowCatalogItem[],
}))

vi.mock("@/features/pipeline/state/useWorkflowTemplates", () => ({
  useWorkflowTemplates: () => ({
    error: "",
    loading: false,
    refresh: mocks.refresh,
    workflows: mocks.workflows,
  }),
}))

vi.mock("@/features/pipeline/layout/useLoadingPresence", () => ({
  useLoadingPresence: () => ({ exiting: false, visible: false }),
}))
;(globalThis as Record<string, unknown>).IS_REACT_ACT_ENVIRONMENT = true

describe("WorkflowTemplatesPage", () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mocks.workflows = [
      workflow("official.screenplay_sample", "剧本样片", "screenplay_sample"),
      workflow("official.short_novel", "短中篇小说", "short_novel"),
    ]
  })

  it("opens the correct official or custom configuration from visible entry points", () => {
    const container = document.createElement("div")
    const root = createRoot(container)
    const onDetail = vi.fn()

    act(() =>
      root.render(
        <WorkflowTemplatesPage onDetail={onDetail} onUseTemplate={vi.fn()} />,
      ),
    )

    const officialBody = container.querySelector<HTMLButtonElement>(
      'button[aria-label="查看剧本样片配置"]',
    )
    const shortDetail = Array.from(
      container.querySelectorAll<HTMLButtonElement>("button"),
    ).find((button) => button.textContent?.includes("短中篇小说"))

    expect(officialBody).not.toBeNull()
    expect(shortDetail).toBeDefined()
    act(() => officialBody?.click())
    act(() => shortDetail?.click())

    expect(onDetail).toHaveBeenNthCalledWith(1, "official.screenplay_sample")
    expect(onDetail).toHaveBeenNthCalledWith(2, "official.short_novel")
    act(() => root.unmount())
  })

  it("renders each canonical route with its own stage count", () => {
    const container = document.createElement("div")
    const root = createRoot(container)

    act(() =>
      root.render(
        <WorkflowTemplatesPage onDetail={vi.fn()} onUseTemplate={vi.fn()} />,
      ),
    )

    const pipeline = container.querySelector(
      'ol[aria-label="剧本样片6阶段生产链"]',
    )
    expect(pipeline).not.toBeNull()
    expect(pipeline?.classList.contains("grid")).toBe(false)
    expect(pipeline?.querySelectorAll("li")).toHaveLength(6)
    expect(
      pipeline?.querySelectorAll(".workflow-pipeline-marker"),
    ).toHaveLength(6)

    act(() => root.unmount())
  })
})

function workflow(
  id: string,
  name: string,
  routeId: CreationRouteId,
): CreationWorkflowCatalogItem {
  const labels =
    routeId === "screenplay_sample"
      ? ["样片立项", "人物圣经", "决策节拍", "场景牌组", "剧本正文", "剧本交付"]
      : routeId === "short_novel"
        ? [
            "小说立项",
            "故事地图",
            "人物圣经",
            "章节与段落计划",
            "小说正文",
            "封面",
            "成书交付",
          ]
        : [
            "长篇立项",
            "全书架构",
            "人物圣经",
            "卷册架构",
            "滚动细纲",
            "章节正文",
            "封面",
            "成书交付",
          ]
  return {
    id,
    routeId,
    name,
    source: "official",
    revision: "r3",
    workflowDigest: "a".repeat(64),
    summary: `${name}官方流水线`,
    available: true,
    deliverableKind: routeId === "screenplay_sample" ? "screenplay" : routeId,
    stages: labels.map((label, index) => ({
      stageId: `stage_${index}`,
      label,
      artifactKind: index === labels.length - 1 ? "delivery" : "artifact",
      workbenchKind: "workbench",
      providerTaskKind: index === labels.length - 1 ? null : "task",
      upstreamStageIds: index ? [`stage_${index - 1}`] : [],
      unitization: index === labels.length - 1 ? "deterministic" : "aggregate",
      decisionPolicyRef: `decision.${routeId}.stage_${index}.v1`,
      contextPolicyRef: `context.${routeId}.stage_${index}.v1`,
      collaborationEnabled: false,
    })),
    capabilities: ["runtime_monitoring"],
    exportProfiles: ["markdown"],
    scalePolicy: {
      unit: routeId === "screenplay_sample" ? "minutes" : "characters",
      minimum: 1,
      recommendedFloor: 2,
      recommended: 3,
      recommendedCeiling: 4,
      maximum: 5,
      rationale: "测试规模",
    },
    reviewPolicy: {
      policyId: `review.${routeId}.default`,
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
