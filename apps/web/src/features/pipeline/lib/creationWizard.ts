import type {
  CreationIntentDraft,
  CreationRouteId,
  CreationRouteMeta,
  CreationWorkflowCatalogItem,
  WorkflowRouteMatch,
} from "../contracts/creationWizard"

export const CREATION_ROUTE_META: Record<CreationRouteId, CreationRouteMeta> = {
  screenplay_sample: {
    id: "screenplay_sample",
    label: "剧本样片",
    shortLabel: "剧本",
    unit: "minutes",
    unitLabel: "分钟",
    targetLabel: "目标时长",
    minimum: 3,
    recommendedFloor: 8,
    recommended: 12,
    recommendedCeiling: 15,
    maximum: 30,
    rationale: "以可拍摄时长控制负载，优先验证动作、场景和对白是否成立。",
    stages: [
      "样片立项",
      "人物圣经",
      "决策节拍",
      "场景牌组",
      "剧本正文",
      "剧本交付",
    ],
  },
  short_novel: {
    id: "short_novel",
    label: "短中篇小说",
    shortLabel: "短中篇",
    unit: "characters",
    unitLabel: "字",
    targetLabel: "目标字数",
    minimum: 2_000,
    recommendedFloor: 10_000,
    recommended: 20_000,
    recommendedCeiling: 30_000,
    maximum: 130_000,
    rationale: "以单体收束和读者承诺为中心，篇幅是软目标而不是凑字数任务。",
    stages: [
      "小说立项",
      "故事地图",
      "人物圣经",
      "章节与段落计划",
      "小说正文",
      "封面",
      "成书交付",
    ],
  },
  long_novel: {
    id: "long_novel",
    label: "长篇小说",
    shortLabel: "长篇",
    unit: "characters",
    unitLabel: "字",
    targetLabel: "目标字数",
    minimum: 100_000,
    recommendedFloor: 100_000,
    recommended: 150_000,
    recommendedCeiling: 200_000,
    maximum: 1_000_000,
    rationale:
      "用卷册和滚动细纲管理长期连续性，先以 10–20 万字生产门验证稳定性。",
    stages: [
      "长篇立项",
      "全书架构",
      "人物圣经",
      "卷册架构",
      "滚动细纲",
      "章节正文",
      "封面",
      "成书交付",
    ],
  },
}

export const DEFAULT_CREATION_INTENT: CreationIntentDraft = {
  creativeIntent: "",
  creationKind: "novel",
  novelLengthClass: "short_novel",
  requestedTarget: CREATION_ROUTE_META.short_novel.recommended,
}

export function routeForIntent(
  intent: Pick<CreationIntentDraft, "creationKind" | "novelLengthClass">,
): CreationRouteId | null {
  if (intent.creationKind === "screenplay") return "screenplay_sample"
  return intent.novelLengthClass
}

export function routeMetaForIntent(intent: CreationIntentDraft) {
  const routeId = routeForIntent(intent)
  return routeId ? CREATION_ROUTE_META[routeId] : null
}

export function targetError(intent: CreationIntentDraft): string {
  const route = routeMetaForIntent(intent)
  if (
    !route ||
    intent.requestedTarget === null ||
    !Number.isFinite(intent.requestedTarget)
  )
    return ""
  if (!Number.isInteger(intent.requestedTarget))
    return `${route.targetLabel}请输入整数。`
  if (
    intent.requestedTarget < route.minimum ||
    intent.requestedTarget > route.maximum
  ) {
    return `${route.targetLabel}需在 ${formatTarget(route.minimum, route.unit)}–${formatTarget(route.maximum, route.unit)} 之间。`
  }
  return ""
}

export function intentError(intent: CreationIntentDraft): string {
  if (!intent.creativeIntent.trim()) return "先写下这部作品想讲什么。"
  if (intent.creativeIntent.trim().length < 20)
    return "创作意图至少写 20 个字符，便于匹配合适的流水线。"
  if (intent.creationKind === "novel" && !intent.novelLengthClass)
    return "请选择小说篇幅。"
  return targetError(intent)
}

export function formatTarget(value: number, unit: CreationRouteMeta["unit"]) {
  if (unit === "minutes") return `${value} 分钟`
  if (value >= 10_000)
    return `${(value / 10_000).toLocaleString("zh-CN", { maximumFractionDigits: 1 })} 万字`
  return `${value.toLocaleString("zh-CN")} 字`
}

export function inferWorkflowRoute(
  workflow: CreationWorkflowCatalogItem,
): CreationRouteId | null {
  return workflow.routeId
}

export function matchWorkflows(
  intent: CreationIntentDraft,
  workflows: CreationWorkflowCatalogItem[],
): WorkflowRouteMatch[] {
  const routeId = routeForIntent(intent)
  if (!routeId) return []
  return workflows
    .filter(
      (workflow) =>
        workflow.available && inferWorkflowRoute(workflow) === routeId,
    )
    .sort((left, right) => {
      const officialDelta =
        Number(left.source === "official") - Number(right.source === "official")
      return officialDelta !== 0
        ? -officialDelta
        : left.name.localeCompare(right.name, "zh-CN")
    })
    .map((workflow, index) => ({
      workflow,
      routeId,
      source: workflow.source,
      matchReason:
        workflow.summary ||
        `${CREATION_ROUTE_META[routeId].label}的生产链，创建后路线会冻结。`,
      recommended: index === 0,
    }))
}

export function routeFromWorkflowId(
  workflowId: string | null,
  workflows: CreationWorkflowCatalogItem[],
) {
  if (!workflowId) return null
  return workflows.find((workflow) => workflow.id === workflowId)
    ? inferWorkflowRoute(
        workflows.find((workflow) => workflow.id === workflowId)!,
      )
    : null
}

export function workflowDisplayName(
  workflow: Pick<CreationWorkflowCatalogItem, "name" | "source">,
  routeId: CreationRouteId,
) {
  return workflow.source === "official"
    ? `${CREATION_ROUTE_META[routeId].label}官方流水线`
    : workflow.name
}
