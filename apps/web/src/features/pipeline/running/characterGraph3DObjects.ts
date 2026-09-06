import * as THREE from "three"
import type {
  CharacterGraphEdge,
  CharacterGraphNode,
} from "../lib/characterGraph"
import { graphEndpointId } from "../lib/characterGraph"

export function createCharacterNodeObject(
  node: CharacterGraphNode,
  options: {
    compact: boolean
    dimmed: boolean
    selected: boolean
    showLabel: boolean
  },
) {
  const group = new THREE.Group()
  const color = options.dimmed ? "#454a48" : node.color
  const radius = Math.max(10, node.val * 1.95)
  const opacity = options.dimmed ? 0.34 : 0.96
  const crystal = new THREE.Mesh(
    nodeGeometry(node, radius),
    new THREE.MeshStandardMaterial({
      color,
      emissive: color,
      emissiveIntensity: options.selected ? 0.9 : options.dimmed ? 0.08 : 0.38,
      metalness: 0.68,
      opacity,
      roughness: 0.18,
      transparent: true,
    }),
  )
  const shell = new THREE.Mesh(
    nodeGeometry(node, radius * 1.28),
    new THREE.MeshBasicMaterial({
      color,
      opacity: options.selected ? 0.5 : options.dimmed ? 0.08 : 0.2,
      transparent: true,
      wireframe: true,
    }),
  )
  const orbit = new THREE.Mesh(
    new THREE.TorusGeometry(
      radius * 1.58,
      options.selected ? 0.4 : 0.22,
      8,
      54,
    ),
    new THREE.MeshBasicMaterial({
      color,
      opacity: options.selected ? 0.86 : options.dimmed ? 0.09 : 0.4,
      transparent: true,
    }),
  )
  orbit.rotation.set(Math.PI / 2.5, 0.28, 0.16)
  const core = new THREE.Mesh(
    new THREE.OctahedronGeometry(radius * 0.45, 1),
    new THREE.MeshBasicMaterial({
      color: "#f7fbf9",
      opacity: options.dimmed ? 0.16 : 0.72,
      transparent: true,
    }),
  )
  group.add(crystal, shell, orbit, core)
  if (options.showLabel)
    group.add(createNodeLabel(node, color, radius, options.compact))
  group.name = `character-node-${node.id}`
  group.userData.characterVisual = true
  return group
}

export function createRelationLabel(
  edge: CharacterGraphEdge,
  options: {
    compact: boolean
    dimmed: boolean
    visible: boolean
  },
) {
  if (!options.visible) return new THREE.Group()
  const canvas = document.createElement("canvas")
  canvas.width = 384
  canvas.height = 72
  const context = canvas.getContext("2d")
  if (!context) return new THREE.Group()
  roundedRect(context, 5, 5, 374, 62, 14)
  context.fillStyle = "rgba(9, 10, 9, 0.88)"
  context.fill()
  context.strokeStyle = `${edge.color}${options.dimmed ? "3f" : "92"}`
  context.lineWidth = 2
  context.stroke()
  context.fillStyle = options.dimmed
    ? "rgba(188, 190, 184, 0.38)"
    : "rgba(240, 241, 235, 0.92)"
  context.font = '600 23px Inter, "Noto Sans SC", sans-serif'
  context.textAlign = "center"
  context.textBaseline = "middle"
  context.fillText(edge.label, 192, 36, 330)

  const texture = new THREE.CanvasTexture(canvas)
  texture.colorSpace = THREE.SRGBColorSpace
  texture.minFilter = THREE.LinearFilter
  const sprite = new THREE.Sprite(
    new THREE.SpriteMaterial({
      depthTest: false,
      depthWrite: false,
      map: texture,
      opacity: options.dimmed ? 0.32 : 0.9,
      transparent: true,
    }),
  )
  sprite.scale.set(options.compact ? 55 : 50, options.compact ? 10.3 : 9.4, 1)
  sprite.renderOrder = 8
  const hash = stableHash(edge.edgeId)
  const lane = (hash % 5) - 2
  sprite.userData.labelOffset =
    (lane === 0 ? 1 : Math.sign(lane)) * (15 + Math.abs(lane) * 7)
  sprite.userData.labelProgress = 0.43 + (hash % 4) * 0.035
  sprite.userData.characterVisual = true
  return sprite
}

export function positionRelationLabel(
  object: THREE.Object3D,
  start: {
    x: number
    y: number
    z: number
  },
  end: {
    x: number
    y: number
    z: number
  },
) {
  const progress = Number(object.userData.labelProgress ?? 0.5)
  const deltaX = end.x - start.x
  const deltaY = end.y - start.y
  const planarLength = Math.max(1, Math.hypot(deltaX, deltaY))
  const offset = Number(object.userData.labelOffset ?? 16)
  object.position.set(
    start.x + deltaX * progress - (deltaY / planarLength) * offset,
    start.y + deltaY * progress + (deltaX / planarLength) * offset,
    start.z + (end.z - start.z) * progress + 6,
  )
  return true
}

export function relationCurve(edge: CharacterGraphEdge) {
  return 0.06 + (stableHash(edge.edgeId) % 3) * 0.035
}

export function relationCurveRotation(edge: CharacterGraphEdge) {
  return ((stableHash(edge.edgeId) % 360) * Math.PI) / 180
}

export function createStaticStarfield(count: number) {
  const positions = new Float32Array(count * 3)
  let seed = 0x79f4a31
  const random = () => {
    seed = (seed * 1664525 + 1013904223) >>> 0
    return seed / 0x100000000
  }
  for (let index = 0; index < count; index += 1) {
    const radius = 680 + random() * 920
    const azimuth = random() * Math.PI * 2
    const polar = Math.acos(2 * random() - 1)
    positions[index * 3] = radius * Math.sin(polar) * Math.cos(azimuth)
    positions[index * 3 + 1] = radius * Math.sin(polar) * Math.sin(azimuth)
    positions[index * 3 + 2] = radius * Math.cos(polar)
  }
  const geometry = new THREE.BufferGeometry()
  geometry.setAttribute("position", new THREE.BufferAttribute(positions, 3))
  const points = new THREE.Points(
    geometry,
    new THREE.PointsMaterial({
      color: "#b7cec9",
      depthWrite: false,
      opacity: 0.25,
      size: 2,
      sizeAttenuation: true,
      transparent: true,
    }),
  )
  points.name = "cast-static-starfield"
  return points
}

export function disposeCharacterObject(object: THREE.Object3D) {
  object.traverse((child) => {
    const mesh = child as THREE.Mesh
    mesh.geometry?.dispose?.()
    const materials = Array.isArray(mesh.material)
      ? mesh.material
      : mesh.material
        ? [mesh.material]
        : []
    materials.forEach((material) => {
      const map = (material as THREE.Material & { map?: THREE.Texture }).map
      map?.dispose()
      material.dispose()
    })
  })
}

function createNodeLabel(
  node: CharacterGraphNode,
  color: string,
  radius: number,
  compact: boolean,
) {
  const canvas = document.createElement("canvas")
  canvas.width = 512
  canvas.height = 124
  const context = canvas.getContext("2d")
  if (!context) return new THREE.Group()
  roundedRect(context, 8, 8, 496, 108, 16)
  context.fillStyle = "rgba(8, 10, 9, 0.9)"
  context.fill()
  context.strokeStyle = `${color}9a`
  context.lineWidth = 3
  context.stroke()
  context.fillStyle = color
  context.fillRect(26, 96, 70, 3)
  context.fillStyle = "#f1f2ed"
  context.font = '700 34px Inter, "Noto Sans SC", sans-serif'
  context.textBaseline = "middle"
  context.fillText(node.name, 28, 43, 440)
  context.fillStyle = "rgba(201, 204, 197, 0.7)"
  context.font = '500 20px Inter, "Noto Sans SC", sans-serif'
  context.fillText(node.role, 28, 78, 440)
  const texture = new THREE.CanvasTexture(canvas)
  texture.colorSpace = THREE.SRGBColorSpace
  texture.minFilter = THREE.LinearFilter
  const sprite = new THREE.Sprite(
    new THREE.SpriteMaterial({
      depthTest: false,
      depthWrite: false,
      map: texture,
      transparent: true,
    }),
  )
  const spatialNode = node as CharacterGraphNode & {
    anchorX?: number
    anchorY?: number
  }
  const horizontalDirection =
    Math.abs(spatialNode.anchorX ?? 0) > 62
      ? -Math.sign(spatialNode.anchorX ?? 0)
      : stableHash(node.id) % 2 === 0
        ? 1
        : -1
  const verticalDirection =
    Math.abs(spatialNode.anchorY ?? 0) > 42
      ? -Math.sign(spatialNode.anchorY ?? 0)
      : 1
  sprite.position.set(
    horizontalDirection * (radius + (compact ? 23 : 27)),
    verticalDirection * (radius + 14),
    0,
  )
  sprite.scale.set(compact ? 82 : 88, compact ? 19.8 : 21.3, 1)
  sprite.renderOrder = 10
  return sprite
}

function nodeGeometry(
  node: CharacterGraphNode,
  radius: number,
): THREE.BufferGeometry {
  if (node.tier === "anchor") return new THREE.DodecahedronGeometry(radius, 1)
  if (node.tier === "hub") return new THREE.OctahedronGeometry(radius, 1)
  if (node.tier === "linked")
    return new THREE.BoxGeometry(
      radius * 1.45,
      radius * 1.45,
      radius * 1.45,
      2,
      2,
      2,
    )
  return new THREE.TetrahedronGeometry(radius, 1)
}

function stableHash(value: string) {
  let hash = 0
  for (let index = 0; index < value.length; index += 1)
    hash = (hash * 31 + value.charCodeAt(index)) >>> 0
  return hash
}

function roundedRect(
  context: CanvasRenderingContext2D,
  x: number,
  y: number,
  width: number,
  height: number,
  radius: number,
) {
  context.beginPath()
  context.roundRect(x, y, width, height, radius)
}
