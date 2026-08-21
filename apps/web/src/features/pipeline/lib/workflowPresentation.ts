import type {
  QualityMode,
  WorkflowDefinition,
  WorkflowStage,
} from "../contracts/workflow"
import {
  isOfficialWorkflowId,
  officialWorkflowOrder,
} from "./officialWorkflows"

export const qualityModeMeta: Record<QualityMode, {
  label: string
  badge: string
  description: string
}> = {
  fast: {
    label: "极速",
    badge: "badge-mint",
    description: "低延迟执行，适合快速推进与自动监控",
  },
  balanced: {
    label: "均衡",
    badge: "badge-balanced",
    description: "兼顾生成质量、速度与运行成本",
  },
  deep: {
    label: "精细",
    badge: "badge-deep",
    description: "提高关键创作节点的推理与生成预算",
  },
}

const stageLabels: Record<string, string> = {
  brief: "简报",
  spine: "脊柱",
  cast: "角色",
  volumes: "卷册",
  detail: "细纲",
  text: "正文",
  cover: "封面",
  export: "导出",
}

export function stageShortLabel(stage: WorkflowStage) {
  return stageLabels[stage.id] ?? stage.label
}

export function workflowDescription(workflow: WorkflowDefinition) {
  const mode = qualityModeMeta[workflow.quality_mode]
  return `${mode.description}。八阶段生产合同与模型绑定会在创建作品后冻结。`
}

export function workflowBadges(workflow: WorkflowDefinition) {
  return [
    isOfficialWorkflowId(workflow.id) ? "官方" : "自定义",
    qualityModeMeta[workflow.quality_mode].label,
  ]
}

export function workflowProviderName(
  workflow: WorkflowDefinition,
  stage: WorkflowStage,
) {
  if (!stage.provider_profile_id) return "系统任务"
  return (
    workflow.provider_profiles.find(
      (profile) => profile.id === stage.provider_profile_id,
    )?.name ?? stage.provider_profile_id
  )
}

export function workflowSort(
  left: WorkflowDefinition,
  right: WorkflowDefinition,
) {
  const leftOfficial = officialWorkflowOrder.indexOf(
    left.id as typeof officialWorkflowOrder[number],
  )
  const rightOfficial = officialWorkflowOrder.indexOf(
    right.id as typeof officialWorkflowOrder[number],
  )
  if (leftOfficial >= 0 || rightOfficial >= 0) {
    if (leftOfficial < 0) return 1
    if (rightOfficial < 0) return -1
    return leftOfficial - rightOfficial
  }
  return left.name.localeCompare(right.name, "zh-CN")
}
