export type ProductionStageRoute = "brief" | "cast" | "beat_board" | "scene_deck" | "script" | "story_map" | "section_plan" | "book_architecture" | "volumes" | "rolling_detail" | "text" | "cover" | "export"

export type Route = /* Studio (no project open) */
"studio" | "workflow-templates" | "history" | "settings" /* New-project wizard */ | "planning" /* Production stages (project open) */ | ProductionStageRoute /* Project tools (project open) */ | "story-bible" | "run-monitor" | "knowledge" | "book-settings" /* Workflow template detail (studio context) */ | "workflow-template-detail"

export type Theme = "light" | "dark"
export type StageStatus = "pending" | "active" | "committed" | "warning" | "blocked" | "failed"

export interface Project {
  architectureVersion: "phase32-routes-v1"
  id: string
  workflowId: string
  latestRunId: string
  creationRouteId: "screenplay_sample" | "short_novel" | "long_novel"
  routeLabel: string
  deliverableKind: string
  activeStageId: string
  stageManifest: Array<{
    id: string
    label: string
    ordinal: number
  }>
  runStatus: string
  progress: {
    completed: number
    total: number
    ratio: number
  }
  targetValue: number
  targetUnit: "minutes" | "characters"
  title: string
  subtitle: string
  author: string
  genre: string
  wordCount: number
  targetWordCount: number
  currentStage: Route
  stageStatuses: Record<string, StageStatus>
  status: "active" | "paused" | "completed"
  createdAt: string
  updatedAt: string
  coverHue: number
}
