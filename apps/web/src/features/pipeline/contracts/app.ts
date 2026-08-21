export type Route = /* Studio (no project open) */
"studio" | "workflow-templates" | "history" | "settings" | /* New-project wizard */
"planning" | /* Production stages (project open) */
"brief" | "spine" | "cast" | "volumes" | "detail" | "text" | "cover" | "export" | /* Project tools (project open) */
"story-bible" | "run-monitor" | "knowledge" | "book-settings" | /* Workflow template detail (studio context) */
"workflow-template-detail"

export type Mode = "fast" | "balanced" | "deep"
export type Theme = "light" | "dark"
export type StageStatus = "pending" | "active" | "committed" | "warning" | "blocked" | "failed"

export interface Project {
  id: string
  workflowId: string
  latestRunId: string
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
