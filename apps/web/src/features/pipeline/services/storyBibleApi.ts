import type {
  ResolvedStoryConflict,
  StoryBibleEvidenceSource,
  StoryBibleFactEntry,
  StoryBibleForeshadowEntry,
  StoryBiblePage,
  StoryBibleSection,
  StoryBibleSummary,
  StoryEpistemicStatus,
  StoryFactLifecycle,
} from "../contracts/storyBible"
import { RunApiError } from "./runApi"

const EPISTEMIC = new Set<StoryEpistemicStatus>([
  "fact",
  "rumour",
  "belief",
  "reveal",
  "refutation",
])
const LIFECYCLES = new Set<StoryFactLifecycle>([
  "active",
  "supersedes",
  "resolves",
  "contradicted",
])
const EVIDENCE_KINDS = new Set([
  "fact",
  "character",
  "relationship",
  "foreshadow",
  "spine",
])
const WRITEBACK_STATUSES = new Set([
  "evidence_only",
  "canon_committed",
  "wiki_projected",
])

export async function getStoryBiblePage<T extends StoryBibleSection>(
  runId: string,
  section: T,
  cursor?: string,
  signal?: AbortSignal,
): Promise<StoryBiblePage<T extends "facts" ? StoryBibleFactEntry : StoryBibleForeshadowEntry>> {
  const query = new URLSearchParams({ section, limit: "50" })
  if (cursor) query.set("cursor", cursor)
  const url = `/api/runs/${encodeURIComponent(runId)}/story-bible?${query}`
  const response = await fetch(url, { signal })
  if (!response.ok) throw await storyBibleResponseError(response)
  return parseStoryBiblePage(await response.json(), runId, section) as StoryBiblePage<
    T extends "facts" ? StoryBibleFactEntry : StoryBibleForeshadowEntry
  >
}

function parseStoryBiblePage(
  value: unknown,
  runId: string,
  section: StoryBibleSection,
): StoryBiblePage<StoryBibleFactEntry | StoryBibleForeshadowEntry> {
  const record = requireRecord(value)
  if (
    record.run_id !== runId ||
    record.section !== section ||
    !Array.isArray(record.items) ||
    !isNonNegativeInteger(record.total) ||
    !isPositiveInteger(record.limit) ||
    Number(record.limit) > 100 ||
    !isNullableString(record.next_cursor)
  )
    throw invalidProjection()
  const summary = parseSummary(record.summary)
  const items =
    section === "facts"
      ? record.items.map(parseFact)
      : record.items.map(parseForeshadow)
  if (items.length > Number(record.limit) || items.length > Number(record.total))
    throw invalidProjection()
  return {
    run_id: runId,
    section,
    summary,
    items,
    total: record.total as number,
    limit: record.limit as number,
    next_cursor: record.next_cursor as string | null,
  }
}

function parseSummary(value: unknown): StoryBibleSummary {
  const record = requireRecord(value)
  if (
    !isNonNegativeInteger(record.evidence_count) ||
    !isNonNegativeInteger(record.canon_fact_count) ||
    !isNonNegativeInteger(record.current_fact_count) ||
    !isNonNegativeInteger(record.wiki_projected_fact_count) ||
    !isNonNegativeInteger(record.foreshadow_count) ||
    !isNonNegativeInteger(record.foreshadow_tracking_count) ||
    !isNonNegativeInteger(record.foreshadow_resolved_count) ||
    !isNullableNonNegativeInteger(record.as_of_chapter) ||
    !Array.isArray(record.conflicts)
  )
    throw invalidProjection()
  return {
    evidence_count: record.evidence_count as number,
    canon_fact_count: record.canon_fact_count as number,
    current_fact_count: record.current_fact_count as number,
    wiki_projected_fact_count: record.wiki_projected_fact_count as number,
    foreshadow_count: record.foreshadow_count as number,
    foreshadow_tracking_count: record.foreshadow_tracking_count as number,
    foreshadow_resolved_count: record.foreshadow_resolved_count as number,
    as_of_chapter: record.as_of_chapter as number | null,
    conflicts: record.conflicts.map(parseConflict),
  }
}

function parseFact(value: unknown): StoryBibleFactEntry {
  const record = requireRecord(value)
  const effectiveFrom = nullablePositiveInteger(record.effective_from_chapter)
  const effectiveTo = nullablePositiveInteger(record.effective_to_chapter)
  if (
    typeof record.is_current !== "boolean" ||
    !Array.isArray(record.evidence_sources)
  )
    throw invalidProjection()
  return {
    fact_id: requiredString(record.fact_id),
    claim: requiredString(record.claim),
    chapter_version_id: requiredString(record.chapter_version_id),
    subject_id: stringValue(record.subject_id),
    property_key: stringValue(record.property_key),
    value: stringValue(record.value),
    epistemic_status: epistemic(record.epistemic_status),
    lifecycle: lifecycle(record.lifecycle),
    effective_from_chapter: effectiveFrom,
    effective_to_chapter: effectiveTo,
    supersedes_fact_ids: stringArray(record.supersedes_fact_ids),
    resolves_fact_ids: stringArray(record.resolves_fact_ids),
    evidence_refs: nonEmptyStringArray(record.evidence_refs),
    evidence_sources: record.evidence_sources.map(parseEvidenceSource),
    missing_evidence_refs: stringArray(record.missing_evidence_refs),
    wiki_transaction_ids: stringArray(record.wiki_transaction_ids),
    is_current: record.is_current,
  }
}

function parseEvidenceSource(value: unknown): StoryBibleEvidenceSource {
  const record = requireRecord(value)
  const kind = requiredString(record.kind)
  if (!EVIDENCE_KINDS.has(kind)) throw invalidProjection()
  return {
    evidence_id: requiredString(record.evidence_id),
    chapter_id: requiredString(record.chapter_id),
    chapter_version_id: requiredString(record.chapter_version_id),
    kind: kind as StoryBibleEvidenceSource["kind"],
    claim: requiredString(record.claim),
    quotes: stringArray(record.quotes),
    created_at: requiredString(record.created_at),
  }
}

function parseConflict(value: unknown): ResolvedStoryConflict {
  const record = requireRecord(value)
  const factIds = nonEmptyStringArray(record.fact_ids)
  const values = nonEmptyStringArray(record.values)
  if (factIds.length < 2 || values.length < 2) throw invalidProjection()
  return {
    subject_id: requiredString(record.subject_id),
    property_key: requiredString(record.property_key),
    fact_ids: factIds,
    values,
  }
}

function parseForeshadow(value: unknown): StoryBibleForeshadowEntry {
  const record = requireRecord(value)
  const writeback = requiredString(record.writeback_status)
  if (!WRITEBACK_STATUSES.has(writeback)) throw invalidProjection()
  return {
    evidence_id: requiredString(record.evidence_id),
    claim: requiredString(record.claim),
    chapter_id: requiredString(record.chapter_id),
    chapter_version_id: requiredString(record.chapter_version_id),
    quotes: stringArray(record.quotes),
    epistemic_status: epistemic(record.epistemic_status),
    lifecycle: lifecycle(record.lifecycle),
    effective_from_chapter: nullablePositiveInteger(record.effective_from_chapter),
    effective_to_chapter: nullablePositiveInteger(record.effective_to_chapter),
    supersedes_fact_ids: stringArray(record.supersedes_fact_ids),
    resolves_fact_ids: stringArray(record.resolves_fact_ids),
    fact_ids: stringArray(record.fact_ids),
    wiki_transaction_ids: stringArray(record.wiki_transaction_ids),
    writeback_status: writeback as StoryBibleForeshadowEntry["writeback_status"],
  }
}

function epistemic(value: unknown): StoryEpistemicStatus {
  const result = requiredString(value) as StoryEpistemicStatus
  if (!EPISTEMIC.has(result)) throw invalidProjection()
  return result
}

function lifecycle(value: unknown): StoryFactLifecycle {
  const result = requiredString(value) as StoryFactLifecycle
  if (!LIFECYCLES.has(result)) throw invalidProjection()
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

function nonEmptyStringArray(value: unknown) {
  const result = stringArray(value)
  if (!result.length || result.some((item) => !item.trim()))
    throw invalidProjection()
  return result
}

function nullablePositiveInteger(value: unknown) {
  if (value === null) return null
  if (!Number.isInteger(value) || Number(value) < 1) throw invalidProjection()
  return value as number
}

function isNullableNonNegativeInteger(value: unknown) {
  return value === null || isNonNegativeInteger(value)
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
      const detail = payload.detail as { code?: unknown; message?: unknown }
      if (typeof detail.code === "string") code = detail.code
      if (typeof detail.message === "string") message = detail.message
    }
  } catch {
    // Keep the stable user-facing fallback for non-JSON errors.
  }
  return new RunApiError(message, response.status, code)
}
