export type ProjectStatus = "active" | "archived"

export type ProjectStageManifest = {
  ordinal: number
  stage_id: string
  label: string
  artifact_kind: string
  workbench_kind: string
  provider_task_kind: string | null
  upstream_stage_ids: string[]
  downstream_stage_ids: string[]
  unitization: string
  decision_policy_ref: string
  context_policy_ref: string
  collaboration_enabled: boolean
}

export type ProjectActiveStage = {
  stage_id: string
  label: string
  ordinal: number
  total: number
}

export type ProjectRecord = {
  architecture_version: "phase32-routes-v1"
  id: string
  title: string
  summary: string
  accent_hue: number
  workflow_id: string
  status: ProjectStatus
  created_at: string
  updated_at: string
  latest_run_id: string
  creation_route_id: "screenplay_sample" | "short_novel" | "long_novel"
  route_revision: string
  route_label: string
  deliverable_kind: string
  run_status: string
  active_stage: ProjectActiveStage
  stage_manifest: ProjectStageManifest[]
  stage_status: Record<string, string>
  completed_stage_ids: string[]
  progress: {
    completed: number
    total: number
    ratio: number
  }
  target: number
  target_unit: "minutes" | "characters"
  words: number
  provider_usage: Record<string, number>
  pending_decisions: Array<Record<string, unknown>>
  failure: Record<string, unknown> | null
}

export type ProjectSummary = {
  project: ProjectRecord
  latest_run: unknown | null
  title: string
  status: string
  current_stage: {
    id: string
    label: string
    type: string
  }
  completed_stage_ids: string[]
  words: number
  updated_at: string
}
