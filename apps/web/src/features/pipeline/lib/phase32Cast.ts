import type { CreationRouteId } from "../contracts/run"

export type CastCharacterDraft = {
  subject_ref: string
  display_name: string
  role: string
  desire: string
  stakes: string
  constraints: string[]
  voice: string
  arc_scope: string
}

export type CastRelationshipDraft = {
  from_subject_ref: string
  to_subject_ref: string
  pressure: string
  change_trigger: string
}

export type CharacterBibleDraft = {
  characters: CastCharacterDraft[]
  relationships: CastRelationshipDraft[]
}

export type CastDiagnostics = {
  characterCount: number
  isolatedSubjectRefs: string[]
  relationshipCount: number
  relationshipDegree: Map<string, number>
}

export type CastRoutePresentation = {
  arcLabel: string
  eyebrow: string
  lead: string
  nextUse: string
  roleLabel: string
  stakesLabel: string
}

type CastParseResult = {
  artifact: CharacterBibleDraft | null
  error: string
}

const REF_PATTERN = /^[a-z][a-z0-9_-]{1,63}$/

export function parsePhase32Cast(
  payload: Record<string, unknown> | null,
): CastParseResult {
  if (!payload)
    return { artifact: null, error: "当前阶段尚无 Character Bible Artifact" }
  if (!exactKeys(payload, ["characters", "relationships"]))
    return { artifact: null, error: "人物圣经包含未知字段或缺少聚合字段" }
  if (
    !Array.isArray(payload.characters) ||
    !Array.isArray(payload.relationships)
  )
    return { artifact: null, error: "人物与关系字段必须使用列表结构" }

  const characters = payload.characters.map(parseCharacter)
  const relationships = payload.relationships.map(parseRelationship)
  if (characters.some((item) => item === null))
    return { artifact: null, error: "人物记录字段不完整" }
  if (relationships.some((item) => item === null))
    return { artifact: null, error: "人物关系字段不完整" }

  const artifact: CharacterBibleDraft = {
    characters: characters as CastCharacterDraft[],
    relationships: relationships as CastRelationshipDraft[],
  }
  return { artifact, error: validateCast(artifact) }
}

export function castDiagnostics(
  artifact: CharacterBibleDraft,
): CastDiagnostics {
  const relationshipDegree = new Map(
    artifact.characters.map((character) => [character.subject_ref, 0]),
  )
  artifact.relationships.forEach((relationship) => {
    relationshipDegree.set(
      relationship.from_subject_ref,
      (relationshipDegree.get(relationship.from_subject_ref) ?? 0) + 1,
    )
    relationshipDegree.set(
      relationship.to_subject_ref,
      (relationshipDegree.get(relationship.to_subject_ref) ?? 0) + 1,
    )
  })
  return {
    characterCount: artifact.characters.length,
    isolatedSubjectRefs: artifact.characters
      .filter((character) => !relationshipDegree.get(character.subject_ref))
      .map((character) => character.subject_ref),
    relationshipCount: artifact.relationships.length,
    relationshipDegree,
  }
}

export function castRoutePresentation(
  routeId: CreationRouteId,
): CastRoutePresentation {
  if (routeId === "screenplay_sample") {
    return {
      arcLabel: "样片内可见变化",
      eyebrow: "SCREENPLAY SAMPLE · CHARACTER BIBLE",
      lead: "冻结屏幕上必须成立的人物目标、限制、对白声纹与关系压力。",
      nextUse: "Beat Board、Scene Deck 与 Script 将只引用这里冻结的人物身份。",
      roleLabel: "屏幕职责",
      stakesLabel: "台面利害",
    }
  }
  if (routeId === "long_novel") {
    return {
      arcLabel: "全书弧线范围",
      eyebrow: "LONG NOVEL · CHARACTER BIBLE",
      lead: "校准人物在 Book、Part 与后续卷册中的长期职责、限制和变化边界。",
      nextUse: "Volumes、Rolling Detail 与正文只能引用这里冻结的 subject ref。",
      roleLabel: "全书职责",
      stakesLabel: "长期利害",
    }
  }
  return {
    arcLabel: "单体弧线范围",
    eyebrow: "SHORT / MEDIUM NOVEL · CHARACTER BIBLE",
    lead: "在有限篇幅内确认必要人物、欲望、代价、声音差异与关系转折空间。",
    nextUse: "Section Plan 与正文将以这里冻结的人物身份组织出场和变化。",
    roleLabel: "故事职责",
    stakesLabel: "失败代价",
  }
}

export function shortCastRef(value: string) {
  return value.length > 32 ? `${value.slice(0, 17)}…${value.slice(-8)}` : value
}

function parseCharacter(value: unknown): CastCharacterDraft | null {
  if (!isRecord(value)) return null
  const fields = [
    "subject_ref",
    "display_name",
    "role",
    "desire",
    "stakes",
    "constraints",
    "voice",
    "arc_scope",
  ] as const
  if (
    !exactKeys(value, fields) ||
    !fields
      .filter((field) => field !== "constraints")
      .every((field) => typeof value[field] === "string") ||
    !Array.isArray(value.constraints) ||
    !value.constraints.every((item) => typeof item === "string")
  )
    return null
  return value as CastCharacterDraft
}

function parseRelationship(value: unknown): CastRelationshipDraft | null {
  if (!isRecord(value)) return null
  const fields = [
    "from_subject_ref",
    "to_subject_ref",
    "pressure",
    "change_trigger",
  ] as const
  if (
    !exactKeys(value, fields) ||
    !fields.every((field) => typeof value[field] === "string")
  )
    return null
  return value as CastRelationshipDraft
}

function validateCast(artifact: CharacterBibleDraft) {
  if (artifact.characters.length < 1 || artifact.characters.length > 120)
    return "人物数量必须在 1 到 120 之间"
  if (artifact.relationships.length > 360) return "人物关系不能超过 360 条"
  const refs = artifact.characters.map((character) => character.subject_ref)
  if (new Set(refs).size !== refs.length) return "人物 subject ref 不能重复"
  for (const [index, character] of artifact.characters.entries()) {
    if (!REF_PATTERN.test(character.subject_ref))
      return `人物 ${index + 1} 的 subject ref 无效`
    if (
      !nonEmpty(character.display_name) ||
      !nonEmpty(character.role) ||
      !nonEmpty(character.desire) ||
      !nonEmpty(character.stakes) ||
      !nonEmpty(character.voice) ||
      !nonEmpty(character.arc_scope)
    )
      return `人物 ${index + 1} 存在未完成的核心字段`
    if (
      character.constraints.length < 1 ||
      character.constraints.length > 16 ||
      character.constraints.some((constraint) => !nonEmpty(constraint))
    )
      return `人物 ${index + 1} 的限制条件必须包含 1 到 16 条有效文本`
  }
  const knownRefs = new Set(refs)
  const edgeKeys = new Set<string>()
  for (const [index, relationship] of artifact.relationships.entries()) {
    const edgeKey = `${relationship.from_subject_ref}\u0000${relationship.to_subject_ref}`
    if (
      !knownRefs.has(relationship.from_subject_ref) ||
      !knownRefs.has(relationship.to_subject_ref) ||
      relationship.from_subject_ref === relationship.to_subject_ref
    )
      return `关系 ${index + 1} 引用了未知或相同人物`
    if (edgeKeys.has(edgeKey)) return `关系 ${index + 1} 的方向端点重复`
    edgeKeys.add(edgeKey)
    if (
      !nonEmpty(relationship.pressure) ||
      !nonEmpty(relationship.change_trigger)
    )
      return `关系 ${index + 1} 存在未完成的压力或变化触发条件`
  }
  return ""
}

function exactKeys(
  value: Record<string, unknown>,
  expected: readonly string[],
) {
  const actual = Object.keys(value).sort()
  const keys = [...expected].sort()
  return (
    actual.length === keys.length &&
    actual.every((key, index) => key === keys[index])
  )
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return Boolean(value) && typeof value === "object" && !Array.isArray(value)
}

function nonEmpty(value: string) {
  return Boolean(value.trim())
}
