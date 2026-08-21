export type ProjectStatus = "active" | "archived"

export type ProjectRecord = {
  id: string
  title: string
  summary: string
  accent_hue: number
  workflow_id: string
  status: ProjectStatus
  created_at: string
  updated_at: string
  latest_run_id: string
}

export type ProjectSummary = {
  project: ProjectRecord
  latest_run: unknown | null
  title: string
  status: string
  current_stage: { id?: string; label?: string; type?: string }
  completed_stage_ids: string[]
  words: number
  updated_at: string
}
