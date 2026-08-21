import type {
  CharacterBibleArtifact,
  CharacterKind,
  CharacterRelation,
  CharacterSubject,
} from "../contracts/artifacts"

export type CharacterGraphNode = CharacterSubject & {
  color: string
  val: number
}

export type CharacterGraphEdge = CharacterRelation & {
  source: string | CharacterGraphNode
  target: string | CharacterGraphNode
  color: string
  label: string
  strength: number
}

export type CharacterGraph = {
  nodes: CharacterGraphNode[]
  links: CharacterGraphEdge[]
}

export const CHARACTER_KIND_META: Record<CharacterKind, {
  badge: string
  color: string
  label: string
  value: number
}> = {
  protagonist: {
    badge: "badge-mint",
    color: "#43c7ad",
    label: "主角",
    value: 6.2,
  },
  major: {
    badge: "badge-amber",
    color: "#d89a42",
    label: "重要角色",
    value: 5.2,
  },
  functional: {
    badge: "badge-fast",
    color: "#6f98dc",
    label: "功能角色",
    value: 4.4,
  },
  npc: { badge: "badge-ash", color: "#9a9590", label: "辅助角色", value: 3.8 },
  historical_record: {
    badge: "badge-deep",
    color: "#9a75c9",
    label: "历史主体",
    value: 4.1,
  },
}

const RELATION_META: Record<string, { color: string; label: string }> = {
  adversarial: { color: "#cb5549", label: "对抗" },
  betrayal: { color: "#c76b55", label: "背叛" },
  captor_captive: { color: "#a875ca", label: "控制" },
  familial_bond: { color: "#45bda2", label: "家族羁绊" },
  familial_conflict: { color: "#d18d3e", label: "家庭冲突" },
  friendship_obligation: { color: "#5f8fd9", label: "友情责任" },
  mentor_student: { color: "#d5a13f", label: "师生" },
  romantic: { color: "#c56f99", label: "情感" },
  rivalry: { color: "#cc654f", label: "竞争" },
}

const FALLBACK_RELATION_COLORS = [
  "#4fbba4",
  "#d29243",
  "#6f98dc",
  "#a77ac9",
  "#c86755",
]

export function projectCharacterGraph(
  artifact: CharacterBibleArtifact,
): CharacterGraph {
  return {
    nodes: artifact.subjects.map((subject) => ({
      ...subject,
      color: CHARACTER_KIND_META[subject.kind].color,
      val: CHARACTER_KIND_META[subject.kind].value,
    })),
    links: artifact.relations.map((relation) => {
      const presentation = relationPresentation(relation.type)
      return {
        ...relation,
        color: presentation.color,
        label: presentation.label,
        source: relation.a,
        strength: relationStrength(relation.pressure),
        target: relation.b,
      }
    }),
  }
}

export function relationPresentation(type: string) {
  const normalized = type.trim().toLowerCase()
  if (RELATION_META[normalized]) return RELATION_META[normalized]
  if (/家|亲|family/.test(type)) return { color: "#45bda2", label: "家庭关系" }
  if (/敌|对抗|rival|advers|hostile/.test(type))
    return { color: "#cb5549", label: "对抗" }
  if (/友|盟|friend|ally/.test(type)) return { color: "#5f8fd9", label: "盟友" }
  if (/师|mentor/.test(type)) return { color: "#d5a13f", label: "师生" }
  if (/背叛|betray/.test(type)) return { color: "#c76b55", label: "背叛" }
  if (/控制|囚|captor|control/.test(type))
    return { color: "#a875ca", label: "控制" }
  const label = /[\u3400-\u9fff]/.test(type) ? type : "人物关系"
  return {
    color:
      FALLBACK_RELATION_COLORS[
        stableHash(normalized) % FALLBACK_RELATION_COLORS.length
      ],
    label,
  }
}

export function graphEndpointId(endpoint: CharacterGraphEdge["source"]) {
  return typeof endpoint === "string" ? endpoint : endpoint.id
}

export function relationTouches(edge: CharacterGraphEdge, subjectId: string) {
  return (
    graphEndpointId(edge.source) === subjectId ||
    graphEndpointId(edge.target) === subjectId
  )
}

export function connectedSubjectIds(graph: CharacterGraph, subjectId: string) {
  const ids = new Set(subjectId ? [subjectId] : [])
  if (!subjectId) return ids
  graph.links.forEach((edge) => {
    const source = graphEndpointId(edge.source)
    const target = graphEndpointId(edge.target)
    if (source === subjectId) ids.add(target)
    if (target === subjectId) ids.add(source)
  })
  return ids
}

function relationStrength(pressure: string) {
  return Math.min(1, 0.56 + pressure.trim().length / 220)
}

function stableHash(value: string) {
  let hash = 0
  for (let index = 0; index < value.length; index += 1) {
    hash = (hash * 31 + value.charCodeAt(index)) >>> 0
  }
  return hash
}
