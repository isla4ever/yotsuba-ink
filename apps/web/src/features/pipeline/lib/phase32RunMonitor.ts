import type {
  Phase32CurrentArtifact,
  Phase32PendingDecision,
  Phase32RunEvent,
  Phase32RunReadModel,
} from "../contracts/run"

export type MonitorField = {
  label: string
  value: string
  wide?: boolean
}

export type MonitorCollectionItem = {
  fields: MonitorField[]
  meta: string
  title: string
}

export type MonitorCollection = {
  items: MonitorCollectionItem[]
  title: string
}

type CollectionPresentation = {
  fields: string[]
  meta: string[]
  title: string[]
}

export type MonitorDocumentBlock = {
  kind: string
  speaker: string
  text: string
}

export type MonitorArtifactProjection = {
  collections: MonitorCollection[]
  document: {
    blocks: MonitorDocumentBlock[]
    paragraphs: string[]
    title: string
  } | null
  eyebrow: string
  fields: MonitorField[]
  title: string
}

export type MonitorUnitState = "active" | "committed" | "failed" | "pending"

const FIELD_LABELS: Record<string, string> = {
  alt_text: "封面描述",
  arc_scope: "变化范围",
  audience_promise: "读者 / 观众承诺",
  author: "作者",
  book_promise: "全书承诺",
  cast_subject_refs: "出场人物",
  chapter_refs: "章节清单",
  chapter_version_refs: "章节版本",
  change_trigger: "关系变化触发",
  character_decision: "人物决定",
  choice_or_revelation: "选择 / 揭示",
  climax: "高潮",
  closure: "收束",
  concept: "视觉命题",
  cover_asset_ref: "正式封面",
  conflict: "冲突",
  consequence_or_open_effect: "结果 / 开放影响",
  constraints: "限制条件",
  dramatic_job: "戏剧任务",
  dramatic_question: "戏剧问题",
  desire: "人物欲望",
  ending_direction: "结局方向",
  ending_effect: "结尾效果",
  ending_state: "结束状态",
  entry_state: "进入状态",
  exit_state: "离开状态",
  formats: "交付格式",
  goal: "目标",
  handoff: "交接",
  heading: "场景标题",
  hook: "章尾钩子",
  image_prompt: "图片 Prompt",
  length_hint: "篇幅提示",
  location: "地点",
  location_and_time: "地点与时间",
  narrative_voice: "叙事声音",
  negative_constraints: "排除项",
  next_window_entry_state: "下一窗口入口",
  open_questions: "开放问题",
  opening_state: "开场状态",
  opposition: "对抗",
  outcome: "结果",
  palette: "色板",
  pov_subject_ref: "视角人物",
  premise: "故事前提",
  pressure: "关系压力",
  promise: "本卷承诺",
  promise_refs: "承诺引用",
  role: "故事职责",
  sample_type: "样片类型",
  scene_refs: "场景清单",
  scene_version_refs: "场景版本",
  scene_load: "场景负载",
  setup_or_payoff_refs: "铺垫 / 回收",
  soft_character_budget: "软字数预算",
  soft_page_target: "软页数目标",
  stakes: "利害",
  selected_asset_ref: "正式选择",
  story_question: "故事问题",
  target_characters: "目标字符",
  target_minutes: "目标时长",
  theme_question: "主题问题",
  time_context: "时间",
  timing_hint: "节奏提示",
  title: "标题",
  tone: "语气",
  turning_point_refs: "转折引用",
  unresolved_obligations: "未兑现义务",
  unit_kind: "单元类型",
  version_note: "版本说明",
  visible_conflict: "可见冲突",
  visible_goal: "可见目标",
  visible_pressure: "可见压力",
  visual_notes: "视觉说明",
  voice: "说话声纹",
  volume_ref: "所属卷",
  volume_refs: "卷册范围",
  world_rules: "世界规则",
}

const INTERNAL_KEYS = new Set([
  "anchor_ref",
  "asset_ref",
  "beat_ref",
  "chapter_ref",
  "from_subject_ref",
  "ordinal",
  "part_ref",
  "scene_ref",
  "subject_ref",
  "to_subject_ref",
  "unit_kind",
  "unit_ref",
  "volume_ref",
  "window_ref",
])

export function projectMonitorArtifact(
  artifact: Phase32CurrentArtifact,
): MonitorArtifactProjection {
  const payload = artifact.payload
  const base = {
    collections: [] as MonitorCollection[],
    document: null as MonitorArtifactProjection["document"],
    eyebrow: `${artifact.artifact_kind} · ${artifact.status}`,
    fields: [] as MonitorField[],
    title: artifactTitle(artifact.artifact_kind, payload),
  }

  if (["short_prose_unit", "chapter"].includes(artifact.artifact_kind)) {
    return {
      ...base,
      document: {
        blocks: [],
        paragraphs: paragraphs(text(payload.content)),
        title: text(payload.title) || base.title,
      },
      fields: fields(payload, ["pov_subject_ref", "unit_kind", "volume_ref"]),
    }
  }

  if (artifact.artifact_kind === "screenplay_draft") {
    return {
      ...base,
      document: {
        blocks: records(payload.blocks).map((block) => ({
          kind: text(block.kind),
          speaker: text(block.speaker_ref),
          text: text(block.text),
        })),
        paragraphs: [],
        title: text(payload.scene_ref) || base.title,
      },
    }
  }

  if (artifact.artifact_kind === "character_bible") {
    return {
      ...base,
      collections: [
        collection("人物", records(payload.characters), {
          fields: [
            "role",
            "desire",
            "stakes",
            "constraints",
            "voice",
            "arc_scope",
          ],
          meta: ["subject_ref"],
          title: ["display_name", "subject_ref"],
        }),
        collection("关系压力", records(payload.relationships), {
          fields: ["pressure", "change_trigger"],
          meta: ["from_subject_ref", "to_subject_ref"],
          title: ["from_subject_ref", "to_subject_ref"],
        }),
      ],
    }
  }

  const collectionSpec = collectionForArtifact(artifact.artifact_kind)
  if (collectionSpec) {
    const source = records(payload[collectionSpec.key])
    const collections = [
      collection(collectionSpec.title, source, collectionSpec.presentation),
    ]
    if (artifact.artifact_kind === "detail_plan_index") {
      const chapters = source.flatMap((window) => records(window.chapters))
      collections.push(
        collection("窗口内章节", chapters, {
          fields: [
            "dramatic_job",
            "entry_state",
            "conflict",
            "stakes",
            "exit_state",
            "hook",
            "handoff",
            "length_hint",
          ],
          meta: ["chapter_ref", "volume_ref", "pov_subject_ref"],
          title: ["title", "chapter_ref"],
        }),
      )
    }
    return {
      ...base,
      collections,
      fields: visibleScalarFields(payload, new Set([collectionSpec.key])),
    }
  }

  if (artifact.artifact_kind === "cover") {
    const brief = record(payload.brief)
    return {
      ...base,
      collections: [
        collection("封面候选", records(payload.candidates), {
          fields: ["alt_text", "visual_notes"],
          meta: ["asset_ref"],
          title: ["alt_text", "asset_ref"],
        }),
      ],
      fields: [
        ...fields(brief, [
          "concept",
          "palette",
          "image_prompt",
          "negative_constraints",
        ]),
        ...field(payload, "image_acceptance_status"),
        ...field(payload, "selected_asset_ref"),
      ],
    }
  }

  return {
    ...base,
    fields: visibleScalarFields(payload),
  }
}

export function monitorUnitState(
  readModel: Phase32RunReadModel,
  stageId: string,
  unitRef: string,
): MonitorUnitState {
  if (
    readModel.failure?.stage_id === stageId &&
    readModel.failure.unit_ref === unitRef
  )
    return "failed"
  if (
    readModel.active_stage_id === stageId &&
    readModel.active_unit_ref === unitRef
  )
    return "active"
  if (
    readModel.sequential_stage_progress[stageId]?.committed_artifact_refs[
      unitRef
    ]
  )
    return "committed"
  return "pending"
}

export function preferredMonitorUnit(
  readModel: Phase32RunReadModel,
  stageId: string,
  decisions: Phase32PendingDecision[],
) {
  const progress = readModel.sequential_stage_progress[stageId]
  const ordered = progress?.ordered_unit_refs ?? []
  if (!ordered.length)
    return decisions.find((item) => item.stage_id === stageId)?.unit_ref ?? ""
  if (
    readModel.active_stage_id === stageId &&
    ordered.includes(readModel.active_unit_ref)
  )
    return readModel.active_unit_ref
  const decisionUnit = decisions.find((item) => item.stage_id === stageId)
    ?.unit_ref
  if (decisionUnit && ordered.includes(decisionUnit)) return decisionUnit
  return (
    [...ordered]
      .reverse()
      .find((unitRef) => progress.committed_artifact_refs[unitRef]) ??
    ordered[0]
  )
}

export function monitorUnitRefs(
  readModel: Phase32RunReadModel,
  stageId: string,
) {
  const ordered =
    readModel.sequential_stage_progress[stageId]?.ordered_unit_refs ?? []
  const discovered = [
    ...ordered,
    ...readModel.pending_decisions
      .filter((item) => item.stage_id === stageId)
      .map((item) => item.unit_ref),
    readModel.active_stage_id === stageId ? readModel.active_unit_ref : "",
  ].filter(Boolean)
  return [...new Set(discovered)]
}

export function eventCategory(event: Phase32RunEvent) {
  if (event.type.includes("failed") || event.type.includes("recovery_required"))
    return "failure"
  if (event.type.startsWith("evidence.")) return "evidence"
  if (event.type.startsWith("writeback.")) return "writeback"
  if (event.type.startsWith("review.")) return "review"
  if (event.type === "checkpoint.saved") return "checkpoint"
  return "lifecycle"
}

function collectionForArtifact(kind: string) {
  const specs: Record<string, {
    key: string
    presentation: {
      fields: string[]
      meta: string[]
      title: string[]
    }
    title: string
  }> = {
    beat_board: {
      key: "beats",
      presentation: {
        fields: [
          "dramatic_job",
          "visible_pressure",
          "character_decision",
          "outcome",
          "setup_or_payoff_refs",
          "timing_hint",
        ],
        meta: ["beat_ref"],
        title: ["dramatic_job", "beat_ref"],
      },
      title: "决策节拍",
    },
    scene_deck: {
      key: "scenes",
      presentation: {
        fields: [
          "location_and_time",
          "cast_subject_refs",
          "visible_goal",
          "opposition",
          "outcome",
          "soft_page_target",
        ],
        meta: ["scene_ref"],
        title: ["heading", "scene_ref"],
      },
      title: "场景牌组",
    },
    story_map: {
      key: "anchors",
      presentation: {
        fields: [
          "dramatic_job",
          "pressure",
          "choice_or_revelation",
          "consequence_or_open_effect",
          "promise_refs",
        ],
        meta: ["anchor_ref"],
        title: ["dramatic_job", "anchor_ref"],
      },
      title: "故事锚点",
    },
    section_plan: {
      key: "units",
      presentation: {
        fields: [
          "dramatic_job",
          "pov_subject_ref",
          "scene_load",
          "handoff",
          "soft_character_budget",
          "promise_refs",
        ],
        meta: ["unit_ref"],
        title: ["title", "unit_ref"],
      },
      title: "章节 / 段落单元",
    },
    book_architecture: {
      key: "parts",
      presentation: {
        fields: [
          "entry_state",
          "dramatic_question",
          "promise_refs",
          "turning_point_refs",
          "exit_state",
          "unresolved_obligations",
        ],
        meta: ["part_ref"],
        title: ["dramatic_question", "part_ref"],
      },
      title: "Part 架构",
    },
    volume_architecture: {
      key: "volumes",
      presentation: {
        fields: [
          "promise",
          "conflict",
          "climax",
          "closure",
          "cast_subject_refs",
          "length_hint",
        ],
        meta: ["volume_ref", "part_ref"],
        title: ["promise", "volume_ref"],
      },
      title: "卷册合同",
    },
    detail_plan_index: {
      key: "windows",
      presentation: {
        fields: [
          "volume_refs",
          "entry_state",
          "handoff",
          "next_window_entry_state",
        ],
        meta: ["window_ref"],
        title: ["window_ref"],
      },
      title: "滚动窗口",
    },
  }
  return specs[kind]
}

function collection(
  title: string,
  source: Record<string, unknown>[],
  presentation: CollectionPresentation,
): MonitorCollection {
  return {
    items: source.map((item, index) => ({
      fields: fields(item, presentation.fields),
      meta: presentation.meta
        .map((key) => text(item[key]))
        .filter(Boolean)
        .join(" · "),
      title:
        presentation.title.map((key) => text(item[key])).find(Boolean) ??
        `${title} ${index + 1}`,
    })),
    title,
  }
}

function fields(value: Record<string, unknown>, keys: string[]) {
  return keys.flatMap((key) => field(value, key))
}

function field(value: Record<string, unknown>, key: string): MonitorField[] {
  const content = displayValue(value[key])
  if (!content) return []
  return [
    {
      label: FIELD_LABELS[key] ?? key,
      value: content,
      wide: content.length > 90,
    },
  ]
}

function visibleScalarFields(
  payload: Record<string, unknown>,
  excluded = new Set<string>(),
) {
  return Object.keys(payload)
    .filter((key) => !excluded.has(key) && !INTERNAL_KEYS.has(key))
    .flatMap((key) => field(payload, key))
}

function artifactTitle(kind: string, payload: Record<string, unknown>) {
  if (text(payload.title)) return text(payload.title)
  const titles: Record<string, string> = {
    beat_board: "决策节拍",
    book_architecture: "全书架构",
    book_delivery: "成书交付",
    chapter: "章节正文",
    character_bible: "人物圣经",
    cover: "封面方案",
    detail_plan_index: "滚动细纲",
    novel_brief: "小说立项",
    scene_deck: "场景牌组",
    screenplay_brief: "样片立项",
    screenplay_draft: "剧本正文",
    script_delivery: "剧本交付",
    section_plan: "章节与段落计划",
    short_prose_unit: "小说正文",
    story_map: "故事地图",
    volume_architecture: "卷册架构",
  }
  return titles[kind] ?? "阶段内容"
}

function displayValue(value: unknown) {
  if (typeof value === "string") return value.trim()
  if (typeof value === "number") return value.toLocaleString("zh-CN")
  if (typeof value === "boolean") return value ? "是" : "否"
  if (Array.isArray(value) && value.every((item) => typeof item === "string"))
    return value.filter(Boolean).join(" · ")
  return ""
}

function paragraphs(value: string) {
  return value
    .split(/\n\s*\n/)
    .map((item) => item.trim())
    .filter(Boolean)
}

function records(value: unknown): Record<string, unknown>[] {
  return Array.isArray(value)
    ? value.filter(
        (item): item is Record<string, unknown> =>
          Boolean(item) && typeof item === "object" && !Array.isArray(item),
      )
    : []
}

function record(value: unknown): Record<string, unknown> {
  return value && typeof value === "object" && !Array.isArray(value)
    ? value as Record<string, unknown>
    : {}
}

function text(value: unknown) {
  return typeof value === "string" ? value : ""
}
