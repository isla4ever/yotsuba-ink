import { describe, expect, it } from "vitest"
import type {
  CreationIntentDraft,
  CreationRouteId,
  CreationWorkflowCatalogItem,
} from "../contracts/creationWizard"
import {
  CREATION_ROUTE_META,
  inferWorkflowRoute,
  matchWorkflows,
  routeForIntent,
  targetError,
  workflowDisplayName,
} from "./creationWizard"

describe("creation wizard route matching", () => {
  it("derives screenplay and novel routes from the first-step intent", () => {
    expect(
      routeForIntent({ creationKind: "screenplay", novelLengthClass: null }),
    ).toBe("screenplay_sample")
    expect(
      routeForIntent({ creationKind: "novel", novelLengthClass: "long_novel" }),
    ).toBe("long_novel")
  })

  it("keeps targets inside the route-owned scale envelope", () => {
    const longIntent: CreationIntentDraft = {
      creativeIntent: "一部以失踪档案和家族秘密为核心的长期悬疑故事。",
      creationKind: "novel",
      novelLengthClass: "long_novel",
      requestedTarget: CREATION_ROUTE_META.long_novel.minimum - 1,
    }
    expect(targetError(longIntent)).toContain("10 万字")
    expect(targetError({ ...longIntent, requestedTarget: 150_000 })).toBe("")
  })

  it("projects the canonical Phase 32 stage order for both novel routes", () => {
    expect(CREATION_ROUTE_META.screenplay_sample.stages).toEqual([
      "样片立项",
      "人物圣经",
      "决策节拍",
      "场景牌组",
      "剧本正文",
      "剧本交付",
    ])
    expect(CREATION_ROUTE_META.short_novel.stages).toEqual([
      "小说立项",
      "故事地图",
      "人物圣经",
      "章节与段落计划",
      "小说正文",
      "封面",
      "成书交付",
    ])
    expect(CREATION_ROUTE_META.long_novel.stages).toEqual([
      "长篇立项",
      "全书架构",
      "人物圣经",
      "卷册架构",
      "滚动细纲",
      "章节正文",
      "封面",
      "成书交付",
    ])
  })

  it("filters by route and keeps official templates ahead of custom ones", () => {
    const intent: CreationIntentDraft = {
      creativeIntent:
        "一名夜班调度员接到来自未来的报警电话，并发现每次干预都会改变家人的命运。",
      creationKind: "novel",
      novelLengthClass: "short_novel",
      requestedTarget: 20_000,
    }
    const matches = matchWorkflows(intent, [
      workflow("custom-short", "我的短篇流水线", "short_novel", "custom"),
      workflow("official.short_novel", "短中篇小说", "short_novel"),
      workflow("official.long_novel", "长篇小说", "long_novel"),
    ])
    expect(matches.map((match) => match.workflow.id)).toEqual([
      "official.short_novel",
      "custom-short",
    ])
    expect(matches[0].recommended).toBe(true)
    expect(matches[1].recommended).toBe(false)
    expect(
      inferWorkflowRoute(
        workflow(
          "custom-screenplay",
          "我的剧本样片",
          "screenplay_sample",
          "custom",
        ),
      ),
    ).toBe("screenplay_sample")
    expect(workflowDisplayName(matches[0].workflow, matches[0].routeId)).toBe(
      "短中篇小说官方流水线",
    )
    expect(workflowDisplayName(matches[1].workflow, matches[1].routeId)).toBe(
      "我的短篇流水线",
    )
  })

  it("recognizes canonical Phase 32 route identities", () => {
    expect(
      inferWorkflowRoute(
        workflow(
          "official.screenplay_sample",
          "剧本样片官方流水线",
          "screenplay_sample",
        ),
      ),
    ).toBe("screenplay_sample")
    expect(
      workflowDisplayName(
        workflow("official.long_novel", "长篇小说", "long_novel"),
        "long_novel",
      ),
    ).toBe("长篇小说官方流水线")
  })
})

function workflow(
  id: string,
  name: string,
  routeId: CreationRouteId,
  source: "official" | "custom" = "official",
): CreationWorkflowCatalogItem {
  return {
    id,
    routeId,
    name,
    source,
    revision: "r3",
    workflowDigest: "a".repeat(64),
    summary: `${name}官方流水线`,
    available: true,
    deliverableKind: routeId === "screenplay_sample" ? "screenplay" : routeId,
    stages: [],
    capabilities: [],
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
