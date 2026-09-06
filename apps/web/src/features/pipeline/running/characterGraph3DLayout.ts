import type { CharacterGraphNode } from "../lib/characterGraph"

export type SpatialCharacterNode = CharacterGraphNode & {
  anchorX?: number
  anchorY?: number
  anchorZ?: number
  vx?: number
  vy?: number
  vz?: number
  x?: number
  y?: number
  z?: number
}

export type CharacterCameraFrame = {
  distance: number
  target: {
    x: number
    y: number
    z: number
  }
}

const GOLDEN_ANGLE = 2.399963229728653

export function initialCharacterLayout(
  nodes: CharacterGraphNode[],
  portrait: boolean,
): SpatialCharacterNode[] {
  const scaleX = portrait ? 0.58 : 1
  const scaleY = portrait ? 1.12 : 1
  const scaleZ = portrait ? 0.62 : 1
  let protagonistIndex = 0
  let peripheralIndex = 0

  return nodes.map((node) => {
    if (node.tier === "anchor") {
      const angle = protagonistIndex * GOLDEN_ANGLE - Math.PI / 2
      const radius =
        nodes.filter((item) => item.tier === "anchor").length > 1 ? 44 : 0
      protagonistIndex += 1
      return anchored(
        node,
        Math.cos(angle) * radius * scaleX,
        Math.sin(angle) * radius * scaleY,
        0,
      )
    }

    const ring = Math.floor(peripheralIndex / 8)
    const angle = peripheralIndex * GOLDEN_ANGLE - Math.PI / 2
    const x = Math.cos(angle) * (178 + ring * 96)
    const y = Math.sin(angle) * (136 + ring * 74)
    const z = Math.sin(angle * 1.7) * 68 + ((peripheralIndex % 3) - 1) * 18
    peripheralIndex += 1
    return anchored(node, x * scaleX, y * scaleY, z * scaleZ)
  })
}

export function createCharacterAnchorForce(nodes: SpatialCharacterNode[]) {
  return (alpha: number) => {
    nodes.forEach((node) => {
      node.vx =
        (node.vx ?? 0) + ((node.anchorX ?? 0) - (node.x ?? 0)) * alpha * 0.105
      node.vy =
        (node.vy ?? 0) + ((node.anchorY ?? 0) - (node.y ?? 0)) * alpha * 0.105
      node.vz =
        (node.vz ?? 0) + ((node.anchorZ ?? 0) - (node.z ?? 0)) * alpha * 0.08
    })
  }
}

export function characterCameraFrame(
  nodes: SpatialCharacterNode[],
  width: number,
  height: number,
): CharacterCameraFrame {
  const positioned = nodes.filter(
    (node) =>
      Number.isFinite(node.x) &&
      Number.isFinite(node.y) &&
      Number.isFinite(node.z),
  )
  const target = {
    x: midpoint(positioned.map((node) => node.x ?? 0)),
    y: midpoint(positioned.map((node) => node.y ?? 0)),
    z: midpoint(positioned.map((node) => node.z ?? 0)),
  }
  const aspect = Math.max(0.5, width / Math.max(1, height))
  const tangent = Math.tan((75 * Math.PI) / 360)
  const labelPadding = width < 520 ? 108 : 94
  const horizontal = Math.max(
    112,
    ...positioned.map(
      (node) => Math.abs((node.x ?? 0) - target.x) + labelPadding,
    ),
  )
  const vertical = Math.max(
    92,
    ...positioned.map((node) => Math.abs((node.y ?? 0) - target.y) + 82),
  )
  const depth = Math.max(
    0,
    ...positioned.map((node) => Math.abs((node.z ?? 0) - target.z)),
  )
  return {
    distance: Math.max(
      236,
      Math.round(
        Math.max(horizontal / (tangent * aspect), vertical / tangent) * 1.16 +
          depth +
          28,
      ),
    ),
    target,
  }
}

export function characterCameraBounds(distance: number) {
  return {
    maximum: Math.max(420, distance * 2.4),
    minimum: Math.max(124, distance * 0.5),
  }
}

function anchored(
  node: CharacterGraphNode,
  x: number,
  y: number,
  z: number,
): SpatialCharacterNode {
  return { ...node, anchorX: x, anchorY: y, anchorZ: z, x, y, z }
}

function midpoint(values: number[]) {
  if (!values.length) return 0
  return (Math.min(...values) + Math.max(...values)) / 2
}
