// @vitest-environment happy-dom

import { act } from "react"
import { createRoot } from "react-dom/client"
import { beforeEach, describe, expect, it, vi } from "vitest"
import type {
  QualityMode,
  StageType,
  WorkflowDefinition,
} from "@/features/pipeline/contracts/workflow"
import WorkflowTemplatesPage from "./WorkflowTemplatesPage"

const mocks = vi.hoisted(() => ({
  refresh: vi.fn(),
  remove: vi.fn(),
  workflows: [] as WorkflowDefinition[],
}))

vi.mock("@/features/pipeline/state/useWorkflowTemplates", () => ({
  useWorkflowTemplates: () => ({
    error: "",
    loading: false,
    refresh: mocks.refresh,
    remove: mocks.remove,
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
      workflow("official-deepseek-fast", "DeepSeek 极速创作流水线", "fast"),
      workflow("custom-balanced", "自定义均衡流水线", "balanced"),
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
      'button[aria-label="查看DeepSeek 极速创作流水线配置"]',
    )
    const customEdit = Array.from(
      container.querySelectorAll<HTMLButtonElement>("button"),
    ).find((button) => button.textContent?.includes("编辑配置"))

    expect(officialBody).not.toBeNull()
    expect(customEdit).toBeDefined()
    act(() => officialBody?.click())
    act(() => customEdit?.click())

    expect(onDetail).toHaveBeenNthCalledWith(1, "official-deepseek-fast")
    expect(onDetail).toHaveBeenNthCalledWith(2, "custom-balanced")
    act(() => root.unmount())
  })

  it("renders every template as one continuous eight-stage pipeline", () => {
    const container = document.createElement("div")
    const root = createRoot(container)

    act(() =>
      root.render(
        <WorkflowTemplatesPage onDetail={vi.fn()} onUseTemplate={vi.fn()} />,
      ),
    )

    const pipeline = container.querySelector(
      'ol[aria-label="DeepSeek 极速创作流水线八阶段生产链"]',
    )
    expect(pipeline).not.toBeNull()
    expect(pipeline?.classList.contains("grid")).toBe(false)
    expect(pipeline?.querySelectorAll("li")).toHaveLength(8)
    expect(
      pipeline?.querySelectorAll(".workflow-pipeline-marker"),
    ).toHaveLength(8)

    act(() => root.unmount())
  })
})

const stageIds: StageType[] = [
  "brief",
  "spine",
  "cast",
  "volumes",
  "detail",
  "text",
  "cover",
  "export",
]

function workflow(
  id: string,
  name: string,
  qualityMode: QualityMode,
): WorkflowDefinition {
  return {
    architecture_version: "phase27-vnext",
    id,
    name,
    version: "29.34.0-test",
    is_template: true,
    global_inputs: [],
    provider_profiles: [
      {
        id: "provider-text",
        name: "测试文本 Provider",
        kind: "openai-compatible",
        default_model: "model-test",
        enabled: true,
      },
    ],
    prompt_templates: [],
    quality_mode: qualityMode,
    nodes: stageIds.map((stageId, index) => ({
      id: stageId,
      type: stageId,
      label: stageId,
      provider_profile_id: stageId === "export" ? "" : "provider-text",
      model_settings: {
        model: stageId === "export" ? "" : "model-test",
        temperature: 0.7,
        max_tokens: 4_000,
        top_p: 1,
        timeout_seconds: 120,
      },
      prompt_template_id: `prompt-${stageId}`,
      input_schema: [],
      generation_budget:
        stageId === "export"
          ? null
          : { max_tokens: 4_000, description: `阶段 ${index + 1}` },
    })),
    edges: stageIds.slice(0, -1).map((stageId, index) => ({
      id: `edge-${stageId}`,
      source: stageId,
      target: stageIds[index + 1],
    })),
  }
}
