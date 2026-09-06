import type { ProjectRecord, ProjectSummary } from "../contracts/project"
import type {
  Project,
  Route,
  StageStatus,
} from "@/features/pipeline/contracts/app"

const stageRoutes: Route[] = [
  "brief",
  "cast",
  "beat_board",
  "scene_deck",
  "script",
  "story_map",
  "section_plan",
  "book_architecture",
  "volumes",
  "rolling_detail",
  "text",
  "cover",
  "export",
]

export function projectPresentation(
  project: ProjectRecord,
  summary?: ProjectSummary,
): Project {
  const activeStageId =
    summary?.current_stage.id ?? project.active_stage.stage_id
  const currentStage = stageRoute(activeStageId)
  const completed = new Set(
    summary?.completed_stage_ids ?? project.completed_stage_ids,
  )
  const stageStatuses = Object.fromEntries(
    project.stage_manifest.map((stage) => [
      stage.stage_id,
      stageStatus(
        project.stage_status[stage.stage_id],
        stage.stage_id === activeStageId,
      ),
    ]),
  )
  completed.forEach((stageId) => {
    stageStatuses[stageId] = "committed"
  })
  const words = Math.max(0, summary?.words ?? project.words)
  return {
    architectureVersion: project.architecture_version,
    id: project.id,
    workflowId: project.workflow_id,
    latestRunId: project.latest_run_id,
    creationRouteId: project.creation_route_id,
    routeLabel: project.route_label,
    deliverableKind: project.deliverable_kind,
    activeStageId,
    stageManifest: project.stage_manifest.map((stage) => ({
      id: stage.stage_id,
      label: stage.label,
      ordinal: stage.ordinal,
    })),
    runStatus: project.run_status,
    progress: project.progress,
    targetValue: project.target,
    targetUnit: project.target_unit,
    title: summary?.title || project.title,
    subtitle: project.summary || "尚未填写作品简介",
    author: "",
    genre: project.route_label,
    wordCount: words,
    targetWordCount:
      project.target_unit === "characters"
        ? Math.max(project.target, words)
        : 0,
    currentStage,
    stageStatuses,
    status:
      project.status === "archived"
        ? "paused"
        : project.run_status === "completed"
          ? "completed"
          : "active",
    createdAt: project.created_at,
    updatedAt: summary?.updated_at || project.updated_at,
    coverHue: project.accent_hue,
  }
}

function stageRoute(value?: string): Route {
  return stageRoutes.includes(value as Route) ? value as Route : "brief"
}

function stageStatus(value: string | undefined, active: boolean): StageStatus {
  if (value === "completed") return "committed"
  if (value === "failed") return "failed"
  if (value === "awaiting_decision") return "warning"
  if (value === "running" || (active && value === "available")) return "active"
  return "pending"
}
