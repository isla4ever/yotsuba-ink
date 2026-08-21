import type { ProjectRecord, ProjectSummary } from "../contracts/project"
import type { Project, Route, StageStatus } from "@/features/pipeline/contracts/app"

const stageIds: Route[] = [
  "brief",
  "spine",
  "cast",
  "volumes",
  "detail",
  "text",
  "cover",
  "export",
]

export function projectPresentation(
  project: ProjectRecord,
  summary?: ProjectSummary,
): Project {
  const currentStage = stageId(
    summary?.current_stage.id ?? summary?.current_stage.type,
  )
  const completed = new Set(summary?.completed_stage_ids ?? [])
  const stageStatuses = Object.fromEntries(
    stageIds.map((id) => {
      let status: StageStatus = "pending"
      if (completed.has(id)) status = "committed"
      else if (id === currentStage && summary?.status === "failed")
        status = "failed"
      else if (id === currentStage) status = "active"
      return [id, status]
    }),
  )
  const words = Math.max(0, summary?.words ?? 0)
  return {
    id: project.id,
    workflowId: project.workflow_id,
    latestRunId: project.latest_run_id,
    title: summary?.title || project.title,
    subtitle: project.summary || "尚未填写作品简介",
    author: "",
    genre: "长篇小说",
    wordCount: words,
    targetWordCount: Math.max(100_000, words),
    currentStage,
    stageStatuses,
    status:
      project.status === "archived"
        ? "paused"
        : summary?.status === "completed"
          ? "completed"
          : "active",
    createdAt: project.created_at,
    updatedAt: summary?.updated_at || project.updated_at,
    coverHue: project.accent_hue,
  }
}

function stageId(value?: string): Route {
  return stageIds.includes(value as Route) ? value as Route : "brief"
}
