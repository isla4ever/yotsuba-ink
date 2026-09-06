import type {
  StoryBibleEntry,
  StoryBibleEntryKind,
  StoryBibleEntryStatus,
  StoryBiblePage,
  StoryBibleSection,
  StoryBibleSource,
  StoryBibleSummary,
  StoryBibleWritebackStatus,
} from "../contracts/storyBible"
import type { CreationRouteId } from "../contracts/run"
import { RunApiError } from "./runApi"

const ROUTES = new Set<CreationRouteId>([
  "screenplay_sample",
  "short_novel",
  "long_novel",
])
const SECTIONS = new Set<StoryBibleSection>([
  "overview",
  "cast",
  "structure",
  "units",
  "continuity",
])
const KINDS = new Set<StoryBibleEntryKind>([
  "brief_field",
  "world_rule",
  "character",
  "relationship",
  "beat",
  "scene",
  "story_anchor",
  "section_unit",
  "part",
  "volume",
  "detail_window",
  "chapter_plan",
  "accepted_unit",
  "promise",
  "open_question",
  "handoff",
  "ending_condition",
  "formal_fact",
])
const STATUSES = new Set<StoryBibleEntryStatus>([
  "committed",
  "accepted",
  "tracked",
  "open",
  "planned",
  "verified",
])
const WRITEBACK_STATUSES = new Set<StoryBibleWritebackStatus>([
  "not_started",
  "in_progress",
  "recovery_required",
  "committed",
])

export async function getStoryBiblePage(
  runId: string,
  section: StoryBibleSection,
  cursor?: string,
  signal?: AbortSignal,
): Promise<StoryBiblePage> {
  const query = new URLSearchParams({ section, limit: "50" })
  if (cursor) query.set("cursor", cursor)
  const url = `/api/runs/${encodeURIComponent(runId)}/story-bible?${query}`
  const response = await fetch(url, { signal })
  if (!response.ok) throw await storyBibleResponseError(response)
  return parseStoryBiblePage(await response.json(), runId, section)
}

export function parseStoryBiblePage(
  value: unknown,
  runId: string,
  section: StoryBibleSection,
): StoryBiblePage {
  const record = requireRecord(value)
  const route = requiredString(record.creation_route_id) as CreationRouteId
  if (
    record.architecture_version !== "phase32-routes-v1" ||
    record.run_id !== runId ||
    record.section !== section ||
    !ROUTES.has(route) ||
    !Array.isArray(record.items) ||
    !isNonNegativeInteger(record.total) ||
    !isPositiveInteger(record.limit) ||
    Number(record.limit) > 100 ||
    !isNullableString(record.next_cursor)
  )
    throw invalidProjection()
  const items = record.items.map(parseEntry)
  if (
    items.length > Number(record.limit) ||
    items.length > Number(record.total)
  )
    throw invalidProjection()
  return {
    architecture_version: "phase32-routes-v1",
    run_id: runId,
    project_id: requiredString(record.project_id),
    creation_route_id: route,
    route_revision: requiredString(record.route_revision),
    definition_digest: digest(record.definition_digest),
    section,
    summary: parseSummary(record.summary),
    items,
    total: record.total as number,
    limit: record.limit as number,
    next_cursor: record.next_cursor as string | null,
  }
}

function parseSummary(value: unknown): StoryBibleSummary {
  const record = requireRecord(value)
  const availableSections = stringArray(record.available_sections)
  if (
    availableSections.some(
      (item) => !SECTIONS.has(item as StoryBibleSection),
    ) ||
    new Set(availableSections).size !== availableSections.length ||
    !isCounters(record) ||
    !WRITEBACK_STATUSES.has(
      record.formal_writeback_status as StoryBibleWritebackStatus,
    )
  )
    throw invalidProjection()
  return {
    title: requiredString(record.title),
    route_label: requiredString(record.route_label),
    run_status: requiredString(record.run_status),
    active_stage_id: requiredString(record.active_stage_id),
    updated_at: requiredString(record.updated_at),
    projection_revision: digest(record.projection_revision),
    available_sections: availableSections as StoryBibleSection[],
    source_artifact_count: record.source_artifact_count as number,
    character_count: record.character_count as number,
    relationship_count: record.relationship_count as number,
    structure_count: record.structure_count as number,
    accepted_unit_count: record.accepted_unit_count as number,
    continuity_count: record.continuity_count as number,
    tracked_promise_count: record.tracked_promise_count as number,
    open_question_count: record.open_question_count as number,
    formal_fact_count: record.formal_fact_count as number,
    formal_writeback_status:
      record.formal_writeback_status as StoryBibleWritebackStatus,
  }
}

function parseEntry(value: unknown): StoryBibleEntry {
  const record = requireRecord(value)
  const kind = requiredString(record.kind) as StoryBibleEntryKind
  const status = requiredString(record.status) as StoryBibleEntryStatus
  if (
    !KINDS.has(kind) ||
    !STATUSES.has(status) ||
    (record.authority !== "committed_artifact" &&
      record.authority !== "accepted_unit" &&
      record.authority !== "canon") ||
    record.confidence !== "direct"
  )
    throw invalidProjection()
  return {
    entry_ref: requiredString(record.entry_ref),
    kind,
    title: requiredString(record.title),
    body: stringValue(record.body),
    detail: stringValue(record.detail),
    status,
    ordinal: nullablePositiveInteger(record.ordinal),
    parent_ref: stringValue(record.parent_ref),
    unit_ref: stringValue(record.unit_ref),
    subject_refs: stringArray(record.subject_refs),
    promise_refs: stringArray(record.promise_refs),
    tags: stringArray(record.tags),
    authority: record.authority,
    confidence: "direct",
    source: parseSource(record.source),
  }
}

function parseSource(value: unknown): StoryBibleSource {
  const record = requireRecord(value)
  return {
    stage_id: requiredString(record.stage_id),
    artifact_kind: requiredString(record.artifact_kind),
    artifact_ref: requiredString(record.artifact_ref),
    payload_digest: digest(record.payload_digest),
    source_path: requiredString(record.source_path),
    committed_at: requiredString(record.committed_at),
  }
}

function isCounters(record: Record<string, unknown>) {
  return [
    "source_artifact_count",
    "character_count",
    "relationship_count",
    "structure_count",
    "accepted_unit_count",
    "continuity_count",
    "tracked_promise_count",
    "open_question_count",
    "formal_fact_count",
  ].every((key) => isNonNegativeInteger(record[key]))
}

function digest(value: unknown) {
  const result = requiredString(value)
  if (!/^[a-f0-9]{64}$/.test(result)) throw invalidProjection()
  return result
}

function requiredString(value: unknown) {
  if (typeof value !== "string" || !value.trim()) throw invalidProjection()
  return value
}

function stringValue(value: unknown) {
  if (typeof value !== "string") throw invalidProjection()
  return value
}

function stringArray(value: unknown) {
  if (!Array.isArray(value) || value.some((item) => typeof item !== "string"))
    throw invalidProjection()
  return value as string[]
}

function nullablePositiveInteger(value: unknown) {
  if (value === null) return null
  if (!Number.isInteger(value) || Number(value) < 1) throw invalidProjection()
  return value as number
}

function isPositiveInteger(value: unknown) {
  return Number.isInteger(value) && Number(value) > 0
}

function isNonNegativeInteger(value: unknown) {
  return Number.isInteger(value) && Number(value) >= 0
}

function isNullableString(value: unknown) {
  return value === null || (typeof value === "string" && Boolean(value.trim()))
}

function requireRecord(value: unknown): Record<string, unknown> {
  if (!value || typeof value !== "object" || Array.isArray(value))
    throw invalidProjection()
  return value as Record<string, unknown>
}

function invalidProjection() {
  return new RunApiError("故事圣经接口返回了无法识别的数据。", 502)
}

async function storyBibleResponseError(response: Response) {
  let message = "故事圣经读取失败。"
  let code: string | undefined
  try {
    const payload = (await response.json()) as { detail?: unknown }
    if (typeof payload.detail === "string") message = payload.detail
    else if (payload.detail && typeof payload.detail === "object") {
      const detail = payload.detail as {
        code?: unknown
        message?: unknown
      }
      if (typeof detail.code === "string") code = detail.code
      if (typeof detail.message === "string") message = detail.message
    }
  } catch {
    // Preserve the stable fallback when the server returns a non-JSON error.
  }
  return new RunApiError(message, response.status, code)
}
