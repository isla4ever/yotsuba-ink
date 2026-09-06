import type { CreationRouteId } from "./run"

export type StoryBibleSection = "overview" | "cast" | "structure" | "units" | "continuity"

export type StoryBibleEntryKind = "brief_field" | "world_rule" | "character" | "relationship" | "beat" | "scene" | "story_anchor" | "section_unit" | "part" | "volume" | "detail_window" | "chapter_plan" | "accepted_unit" | "promise" | "open_question" | "handoff" | "ending_condition" | "formal_fact"

export type StoryBibleEntryStatus = "committed" | "accepted" | "tracked" | "open" | "planned" | "verified"

export type StoryBibleWritebackStatus = "not_started" | "in_progress" | "recovery_required" | "committed"

export type StoryBibleSource = {
  stage_id: string
  artifact_kind: string
  artifact_ref: string
  payload_digest: string
  source_path: string
  committed_at: string
}

export type StoryBibleEntry = {
  entry_ref: string
  kind: StoryBibleEntryKind
  title: string
  body: string
  detail: string
  status: StoryBibleEntryStatus
  ordinal: number | null
  parent_ref: string
  unit_ref: string
  subject_refs: string[]
  promise_refs: string[]
  tags: string[]
  authority: "committed_artifact" | "accepted_unit" | "canon"
  confidence: "direct"
  source: StoryBibleSource
}

export type StoryBibleSummary = {
  title: string
  route_label: string
  run_status: string
  active_stage_id: string
  updated_at: string
  projection_revision: string
  available_sections: StoryBibleSection[]
  source_artifact_count: number
  character_count: number
  relationship_count: number
  structure_count: number
  accepted_unit_count: number
  continuity_count: number
  tracked_promise_count: number
  open_question_count: number
  formal_fact_count: number
  formal_writeback_status: StoryBibleWritebackStatus
}

export type StoryBiblePage = {
  architecture_version: "phase32-routes-v1"
  run_id: string
  project_id: string
  creation_route_id: CreationRouteId
  route_revision: string
  definition_digest: string
  section: StoryBibleSection
  summary: StoryBibleSummary
  items: StoryBibleEntry[]
  total: number
  limit: number
  next_cursor: string | null
}
