export type StoryEpistemicStatus =
  | "fact"
  | "rumour"
  | "belief"
  | "reveal"
  | "refutation"

export type StoryFactLifecycle =
  | "active"
  | "supersedes"
  | "resolves"
  | "contradicted"

export type StoryBibleEvidenceSource = {
  evidence_id: string
  chapter_id: string
  chapter_version_id: string
  kind: "fact" | "character" | "relationship" | "foreshadow" | "spine"
  claim: string
  quotes: string[]
  created_at: string
}

export type StoryBibleFactEntry = {
  fact_id: string
  claim: string
  chapter_version_id: string
  subject_id: string
  property_key: string
  value: string
  epistemic_status: StoryEpistemicStatus
  lifecycle: StoryFactLifecycle
  effective_from_chapter: number | null
  effective_to_chapter: number | null
  supersedes_fact_ids: string[]
  resolves_fact_ids: string[]
  evidence_refs: string[]
  evidence_sources: StoryBibleEvidenceSource[]
  missing_evidence_refs: string[]
  wiki_transaction_ids: string[]
  is_current: boolean
}

export type ResolvedStoryConflict = {
  subject_id: string
  property_key: string
  fact_ids: string[]
  values: string[]
}

export type StoryBibleForeshadowEntry = {
  evidence_id: string
  claim: string
  chapter_id: string
  chapter_version_id: string
  quotes: string[]
  epistemic_status: StoryEpistemicStatus
  lifecycle: StoryFactLifecycle
  effective_from_chapter: number | null
  effective_to_chapter: number | null
  supersedes_fact_ids: string[]
  resolves_fact_ids: string[]
  fact_ids: string[]
  wiki_transaction_ids: string[]
  writeback_status: "evidence_only" | "canon_committed" | "wiki_projected"
}

export type StoryBibleSection = "facts" | "foreshadow"

export type StoryBibleSummary = {
  evidence_count: number
  canon_fact_count: number
  current_fact_count: number
  wiki_projected_fact_count: number
  foreshadow_count: number
  foreshadow_tracking_count: number
  foreshadow_resolved_count: number
  as_of_chapter: number | null
  conflicts: ResolvedStoryConflict[]
}

export type StoryBiblePage<T> = {
  run_id: string
  section: StoryBibleSection
  summary: StoryBibleSummary
  items: T[]
  total: number
  limit: number
  next_cursor: string | null
}
