export type BookPartDraft = {
  part_ref: string
  ordinal: number
  entry_state: string
  dramatic_question: string
  promise_refs: string[]
  turning_point_refs: string[]
  exit_state: string
  unresolved_obligations: string[]
}

export type BookArchitectureDraft = {
  book_promise: string
  ending_conditions: string[]
  parts: BookPartDraft[]
}

export type PromiseLifecycleProjection = {
  promiseRef: string
  partRefs: string[]
}

export type BookArchitectureDiagnostics = {
  endingConditionCount: number
  partCount: number
  promiseLifecycle: PromiseLifecycleProjection[]
  turningPointCount: number
  unresolvedObligationCount: number
}

type BookArchitectureParseResult = {
  artifact: BookArchitectureDraft | null
  error: string
}

const REF_PATTERN = /^[a-z][a-z0-9_-]{1,63}$/

export function parsePhase32BookArchitecture(
  payload: Record<string, unknown> | null,
): BookArchitectureParseResult {
  if (!payload)
    return { artifact: null, error: "当前阶段尚无 Book Architecture Artifact" }
  if (
    typeof payload.book_promise !== "string" ||
    !Array.isArray(payload.ending_conditions) ||
    !payload.ending_conditions.every((item) => typeof item === "string") ||
    !Array.isArray(payload.parts)
  )
    return { artifact: null, error: "全书架构字段不完整" }

  const parts = payload.parts.map(parsePart)
  if (parts.some((part) => part === null))
    return { artifact: null, error: "Part 契约字段不完整" }

  const artifact: BookArchitectureDraft = {
    book_promise: payload.book_promise,
    ending_conditions: payload.ending_conditions as string[],
    parts: parts as BookPartDraft[],
  }
  const refs = artifact.parts.map((part) => part.part_ref)
  const invalid =
    !nonEmpty(artifact.book_promise) ||
    artifact.ending_conditions.length === 0 ||
    artifact.ending_conditions.length > 32 ||
    artifact.ending_conditions.some((condition) => !nonEmpty(condition)) ||
    artifact.parts.length === 0 ||
    artifact.parts.length > 24 ||
    new Set(refs).size !== refs.length ||
    artifact.parts.some(
      (part, index) =>
        !REF_PATTERN.test(part.part_ref) ||
        part.ordinal !== index + 1 ||
        !nonEmpty(part.entry_state) ||
        !nonEmpty(part.dramatic_question) ||
        !nonEmpty(part.exit_state) ||
        part.promise_refs.length === 0 ||
        part.promise_refs.length > 32 ||
        part.promise_refs.some((ref) => !REF_PATTERN.test(ref)) ||
        part.turning_point_refs.length === 0 ||
        part.turning_point_refs.length > 32 ||
        part.turning_point_refs.some((ref) => !REF_PATTERN.test(ref)) ||
        part.unresolved_obligations.length > 32 ||
        part.unresolved_obligations.some((item) => !nonEmpty(item)),
    )

  return {
    artifact,
    error: invalid ? "全书架构存在空字段、无效引用、重复 Part 或顺序漂移" : "",
  }
}

export function bookArchitectureDiagnostics(
  artifact: BookArchitectureDraft,
): BookArchitectureDiagnostics {
  const promiseParts = new Map<string, string[]>()
  for (const part of artifact.parts) {
    for (const promiseRef of part.promise_refs) {
      const partRefs = promiseParts.get(promiseRef) ?? []
      if (!partRefs.includes(part.part_ref)) partRefs.push(part.part_ref)
      promiseParts.set(promiseRef, partRefs)
    }
  }
  return {
    endingConditionCount: artifact.ending_conditions.length,
    partCount: artifact.parts.length,
    promiseLifecycle: Array.from(promiseParts, ([promiseRef, partRefs]) => ({
      promiseRef,
      partRefs,
    })),
    turningPointCount: artifact.parts.reduce(
      (total, part) => total + part.turning_point_refs.length,
      0,
    ),
    unresolvedObligationCount: artifact.parts.reduce(
      (total, part) => total + part.unresolved_obligations.length,
      0,
    ),
  }
}

export function reorderBookParts(
  parts: BookPartDraft[],
  index: number,
  offset: -1 | 1,
) {
  const target = index + offset
  if (target < 0 || target >= parts.length) return parts
  const reordered = [...parts]
  ;[reordered[index], reordered[target]] = [reordered[target], reordered[index]]
  return reordered.map((part, partIndex) => ({
    ...part,
    ordinal: partIndex + 1,
  }))
}

function parsePart(value: unknown): BookPartDraft | null {
  if (!isRecord(value)) return null
  const textFields = [
    "part_ref",
    "entry_state",
    "dramatic_question",
    "exit_state",
  ] as const
  if (
    !textFields.every((field) => typeof value[field] === "string") ||
    !Number.isInteger(value.ordinal) ||
    !Array.isArray(value.promise_refs) ||
    !value.promise_refs.every((item) => typeof item === "string") ||
    !Array.isArray(value.turning_point_refs) ||
    !value.turning_point_refs.every((item) => typeof item === "string") ||
    !Array.isArray(value.unresolved_obligations) ||
    !value.unresolved_obligations.every((item) => typeof item === "string")
  )
    return null
  return value as BookPartDraft
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return Boolean(value) && typeof value === "object" && !Array.isArray(value)
}

function nonEmpty(value: string) {
  return Boolean(value.trim())
}
