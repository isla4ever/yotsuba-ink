import type { CreationRouteId } from "../contracts/run"

export type ScreenplayBriefDraft = {
  title: string
  sample_type: string
  target_minutes: number
  premise: string
  audience_promise: string
  visible_conflict: string
  ending_effect: string
  tone: string
}

export type NovelBriefDraft = {
  title: string
  premise: string
  audience_promise: string
  theme_question: string
  world_rules: string[]
  ending_direction: string
  narrative_voice: string
  target_characters: number
}

export type Phase32BriefDraft = {
  kind: "screenplay"
  value: ScreenplayBriefDraft
} | {
  kind: "novel"
  value: NovelBriefDraft
}

type Phase32BriefParseResult = {
  artifact: Phase32BriefDraft | null
  error: string
}

export function parsePhase32Brief(
  routeId: CreationRouteId,
  payload: Record<string, unknown> | null,
): Phase32BriefParseResult {
  if (!payload) return { artifact: null, error: "当前阶段尚无 Brief Artifact" }
  if (routeId === "screenplay_sample") {
    const fields = [
      "title",
      "sample_type",
      "premise",
      "audience_promise",
      "visible_conflict",
      "ending_effect",
      "tone",
    ] as const
    if (
      !fields.every((field) => typeof payload[field] === "string") ||
      !Number.isInteger(payload.target_minutes)
    )
      return { artifact: null, error: "剧本立项稿字段不完整" }
    return {
      artifact: {
        kind: "screenplay",
        value: payload as ScreenplayBriefDraft,
      },
      error: fields.every((field) => nonEmpty(payload[field]))
        ? ""
        : "剧本立项字段不能留空",
    }
  }

  const fields = [
    "title",
    "premise",
    "audience_promise",
    "theme_question",
    "ending_direction",
    "narrative_voice",
  ] as const
  if (
    !fields.every((field) => typeof payload[field] === "string") ||
    !Number.isInteger(payload.target_characters) ||
    !Array.isArray(payload.world_rules) ||
    !payload.world_rules.every((item) => typeof item === "string")
  )
    return { artifact: null, error: "小说立项稿字段不完整" }
  return {
    artifact: {
      kind: "novel",
      value: payload as NovelBriefDraft,
    },
    error:
      fields.every((field) => nonEmpty(payload[field])) &&
      payload.world_rules.length > 0 &&
      payload.world_rules.every(nonEmpty)
        ? ""
        : "小说立项字段与世界规则不能留空",
  }
}

export function splitBriefRules(value: string) {
  return value
    .split("\n")
    .map((item) => item.trim())
    .filter(Boolean)
}

function nonEmpty(value: unknown): value is string {
  return typeof value === "string" && Boolean(value.trim())
}
