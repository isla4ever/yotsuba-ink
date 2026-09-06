import type { CharacterBibleDraft, CastRelationshipDraft } from "./phase32Cast"
import type { CharacterKind } from "../contracts/artifacts"

export type CharacterGraphTier = "anchor" | "hub" | "linked" | "isolated"

export type CharacterGraphNode = {
  id: string
  name: string
  role: string
  tier: CharacterGraphTier
  color: string
  val: number
}

export type CharacterGraphEdge = CastRelationshipDraft & {
  edgeId: string
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

export const CHARACTER_GRAPH_TIER_META: Record<CharacterGraphTier, {
  label: string
  value: number
}> = {
  anchor: { label: "关系锚点", value: 6.2 },
  hub: { label: "关系枢纽", value: 5.2 },
  linked: { label: "关联人物", value: 4.4 },
  isolated: { label: "独立人物", value: 3.9 },
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
    badge: "badge-blue",
    color: "#6f98dc",
    label: "功能角色",
    value: 4.4,
  },
  npc: { badge: "badge-ash", color: "#9a9590", label: "辅助角色", value: 3.8 },
  historical_record: {
    badge: "badge-violet",
    color: "#9a75c9",
    label: "历史主体",
    value: 4.1,
  },
}

const NODE_COLORS = [
  "#55cbb2",
  "#e0a34b",
  "#72a1ea",
  "#be82da",
  "#e06f62",
  "#7dc2d4",
  "#d48baa",
  "#a7bd66",
]

const EDGE_COLORS = ["#5fc6b0", "#d69a4a", "#739fe2", "#b77fd2", "#d66e61"]

export function projectCharacterGraph(
  artifact: CharacterBibleDraft,
): CharacterGraph {
  const degrees = new Map(
    artifact.characters.map((character) => [character.subject_ref, 0]),
  )
  artifact.relationships.forEach((relationship) => {
    degrees.set(
      relationship.from_subject_ref,
      (degrees.get(relationship.from_subject_ref) ?? 0) + 1,
    )
    degrees.set(
      relationship.to_subject_ref,
      (degrees.get(relationship.to_subject_ref) ?? 0) + 1,
    )
  })
  const maximumDegree = Math.max(0, ...degrees.values())
  const anchorRef =
    artifact.characters.find(
      (character) => degrees.get(character.subject_ref) === maximumDegree,
    )?.subject_ref ?? artifact.characters[0]?.subject_ref

  return {
    nodes: artifact.characters.map((character) => {
      const degree = degrees.get(character.subject_ref) ?? 0
      const tier: CharacterGraphTier =
        character.subject_ref === anchorRef
          ? "anchor"
          : degree >= 2
            ? "hub"
            : degree === 1
              ? "linked"
              : "isolated"
      return {
        id: character.subject_ref,
        name: character.display_name,
        role: character.role,
        tier,
        color:
          NODE_COLORS[stableHash(character.subject_ref) % NODE_COLORS.length],
        val: CHARACTER_GRAPH_TIER_META[tier].value,
      }
    }),
    links: artifact.relationships.map((relationship) => ({
      ...relationship,
      edgeId: `${relationship.from_subject_ref}:${relationship.to_subject_ref}`,
      color:
        EDGE_COLORS[
          stableHash(
            `${relationship.from_subject_ref}:${relationship.to_subject_ref}`,
          ) % EDGE_COLORS.length
        ],
      label: "关系压力",
      source: relationship.from_subject_ref,
      strength: Math.min(1, 0.56 + relationship.pressure.trim().length / 220),
      target: relationship.to_subject_ref,
    })),
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

export function graphColorForSubject(subjectRef: string) {
  return NODE_COLORS[stableHash(subjectRef) % NODE_COLORS.length]
}

function stableHash(value: string) {
  let hash = 0
  for (let index = 0; index < value.length; index += 1)
    hash = (hash * 31 + value.charCodeAt(index)) >>> 0
  return hash
}
