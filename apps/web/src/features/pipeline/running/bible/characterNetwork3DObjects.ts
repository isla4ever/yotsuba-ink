import * as THREE from 'three';
import type { CharacterEdge, CharacterNode } from '../../contracts';

type VisualNode = CharacterNode & { anchorX?: number; anchorY?: number; val: number };
export type NodeLabelDetail = 'full' | 'name' | 'hidden';
export type CharacterNodeVisualKind = 'functional' | 'historical_record' | 'major' | 'npc' | 'protagonist';

export function relationshipTouchesNode(edge: CharacterEdge, nodeId: string) {
  return endpointId(edge.source) === nodeId || endpointId(edge.target) === nodeId;
}

export function createCharacterNode3D(
  node: VisualNode,
  color: string,
  selected: boolean,
  options: { compact?: boolean; labelDetail?: NodeLabelDetail } = {},
) {
  const group = new THREE.Group();
  const radius = Math.max(11, node.val * 2.02);
  const visualKind = characterNodeVisualKind(node);
  const crystal = new THREE.Mesh(
    createNodeGeometry(visualKind, radius),
    new THREE.MeshStandardMaterial({
      color,
      emissive: color,
      emissiveIntensity: selected ? 0.82 : 0.34,
      metalness: 0.72,
      opacity: selected ? 1 : 0.94,
      roughness: 0.17,
      transparent: true,
    }),
  );
  const shell = new THREE.Mesh(
    createNodeGeometry(visualKind, radius * 1.28),
    new THREE.MeshBasicMaterial({
      color,
      opacity: selected ? 0.46 : 0.2,
      transparent: true,
      wireframe: true,
    }),
  );
  const orbit = new THREE.Mesh(
    new THREE.TorusGeometry(radius * 1.55, selected ? 0.42 : 0.28, 8, 56),
    new THREE.MeshBasicMaterial({ color, opacity: selected ? 0.9 : 0.52, transparent: true }),
  );
  orbit.rotation.set(Math.PI / 2.5, 0.28, 0.16);
  const polarOrbit = new THREE.Mesh(
    new THREE.TorusGeometry(radius * 1.82, selected ? 0.28 : 0.18, 7, 56),
    new THREE.MeshBasicMaterial({ color, opacity: selected ? 0.62 : 0.27, transparent: true }),
  );
  polarOrbit.rotation.set(0.34, Math.PI / 2.2, -0.2);
  const core = new THREE.Mesh(
    new THREE.OctahedronGeometry(radius * 0.48, 1),
    new THREE.MeshBasicMaterial({ color: '#f6fbf9', opacity: selected ? 0.94 : 0.7, transparent: true }),
  );
  group.add(crystal, core, shell, orbit, polarOrbit);
  group.userData.visualKind = visualKind;
  if (options.labelDetail !== 'hidden') {
    group.add(createNodeLabel(node, color, radius, options.labelDetail ?? 'full', Boolean(options.compact)));
  }
  return group;
}

export function characterNodeVisualKind(node: Pick<CharacterNode, 'status' | 'tier'>): CharacterNodeVisualKind {
  if (node.status === 'historical_record' || node.status === 'historical') return 'historical_record';
  if (node.status === 'functional') return 'functional';
  if (node.status === 'major') return 'major';
  if (node.status === 'npc') return 'npc';
  if (node.status === 'protagonist') return 'protagonist';
  if (node.tier === 'protagonist') return 'protagonist';
  if (node.tier === 'major') return 'major';
  if (node.tier === 'supporting' || node.tier === 'minor') return 'functional';
  return 'npc';
}

function createNodeGeometry(kind: CharacterNodeVisualKind, radius: number): THREE.BufferGeometry {
  if (kind === 'protagonist') return new THREE.DodecahedronGeometry(radius, 1);
  if (kind === 'major') return new THREE.OctahedronGeometry(radius, 1);
  if (kind === 'functional') return new THREE.BoxGeometry(radius * 1.5, radius * 1.5, radius * 1.5, 2, 2, 2);
  if (kind === 'historical_record') return new THREE.CylinderGeometry(radius * 0.7, radius, radius * 1.7, 6, 1);
  return new THREE.TetrahedronGeometry(radius, 1);
}

function createNodeLabel(node: VisualNode, color: string, radius: number, detail: NodeLabelDetail, compact: boolean) {
  const showRole = detail === 'full';
  const canvas = document.createElement('canvas');
  canvas.width = 512;
  canvas.height = showRole ? 128 : 88;
  const context = canvas.getContext('2d');
  if (!context) return new THREE.Sprite();

  drawRoundedRect(context, 8, 8, 496, showRole ? 112 : 72, 18);
  context.fillStyle = 'rgba(5, 9, 9, 0.9)';
  context.fill();
  context.strokeStyle = `${color}aa`;
  context.lineWidth = 3;
  context.stroke();
  context.fillStyle = color;
  context.fillRect(26, showRole ? 100 : 67, 76, 3);
  context.fillStyle = '#f4f8f7';
  context.font = '700 36px Inter, sans-serif';
  context.textBaseline = 'middle';
  context.fillText(node.name, 28, showRole ? 47 : 39, showRole ? 292 : 440);
  if (showRole) {
    context.fillStyle = 'rgba(210, 222, 218, 0.7)';
    context.font = '500 21px Inter, sans-serif';
    context.fillText(node.role || '人物', 28, 83, 440);
  }

  const texture = new THREE.CanvasTexture(canvas);
  texture.colorSpace = THREE.SRGBColorSpace;
  texture.minFilter = THREE.LinearFilter;
  const sprite = new THREE.Sprite(new THREE.SpriteMaterial({
    depthTest: false,
    depthWrite: false,
    map: texture,
    transparent: true,
  }));
  const anchorX = node.anchorX ?? 0;
  const labelDirection = Math.abs(anchorX) > 70 ? -Math.sign(anchorX) : stableDirection(node.id);
  const anchorY = node.anchorY ?? 0;
  const verticalDirection = Math.abs(anchorY) > 42 ? -Math.sign(anchorY) : stableDirection(`${node.id}-vertical`);
  sprite.position.set(
    labelDirection * (radius + (compact ? 26 : 30)),
    verticalDirection * (radius + (showRole ? 18 : 13)),
    0,
  );
  sprite.scale.set(compact ? 86 : 92, showRole ? (compact ? 21.5 : 23) : (compact ? 14.8 : 15.8), 1);
  sprite.renderOrder = 10;
  return sprite;
}

export function createRelationshipLabel3D(
  edge: CharacterEdge,
  color: string,
  options: { compact?: boolean; visible?: boolean } = {},
) {
  if (options.visible === false) return new THREE.Group();
  const canvas = document.createElement('canvas');
  canvas.width = 384;
  canvas.height = 72;
  const context = canvas.getContext('2d');
  if (!context) return new THREE.Sprite();

  drawRoundedRect(context, 5, 5, 374, 62, 16);
  context.fillStyle = 'rgba(4, 7, 7, 0.86)';
  context.fill();
  context.strokeStyle = `${color}70`;
  context.lineWidth = 2;
  context.stroke();
  context.fillStyle = 'rgba(235, 242, 239, 0.9)';
  context.font = '600 23px Inter, sans-serif';
  context.textAlign = 'center';
  context.textBaseline = 'middle';
  context.fillText(edge.relation || '关系', 192, 36, 336);

  const texture = new THREE.CanvasTexture(canvas);
  texture.colorSpace = THREE.SRGBColorSpace;
  texture.minFilter = THREE.LinearFilter;
  const sprite = new THREE.Sprite(new THREE.SpriteMaterial({
    depthTest: false,
    depthWrite: false,
    map: texture,
    opacity: 0.9,
    transparent: true,
  }));
  sprite.scale.set(options.compact ? 58 : 52, options.compact ? 10.9 : 9.75, 1);
  sprite.renderOrder = 8;
  const labelHash = stableHash(`${endpointId(edge.source)}-${endpointId(edge.target)}-${edge.relation}`);
  const lane = labelHash % 5 - 2;
  sprite.userData.labelOffset = (lane === 0 ? 1 : Math.sign(lane)) * (17 + Math.abs(lane) * 8);
  sprite.userData.labelProgress = 0.44 + (labelHash % 4) * 0.035;
  return sprite;
}

export function positionRelationshipLabel(
  object: THREE.Object3D,
  start: { x: number; y: number; z: number },
  end: { x: number; y: number; z: number },
) {
  const progress = Number(object.userData.labelProgress ?? 0.52);
  const deltaX = end.x - start.x;
  const deltaY = end.y - start.y;
  const planarLength = Math.max(1, Math.hypot(deltaX, deltaY));
  const offset = Number(object.userData.labelOffset ?? 18);
  object.position.set(
    start.x + deltaX * progress - (deltaY / planarLength) * offset,
    start.y + deltaY * progress + (deltaX / planarLength) * offset,
    start.z + (end.z - start.z) * progress + 6,
  );
  return true;
}

export function relationshipCurve(edge: CharacterEdge) {
  return 0.07 + (stableHash(`${endpointId(edge.source)}-${endpointId(edge.target)}-${edge.relation}`) % 3) * 0.035;
}

export function relationshipCurveRotation(edge: CharacterEdge) {
  const hash = stableHash(`${endpointId(edge.source)}-${endpointId(edge.target)}-${edge.relation}`);
  return (hash % 360) * Math.PI / 180;
}

function stableDirection(value: string) {
  return stableHash(value) % 2 === 0 ? 1 : -1;
}

function stableHash(value: string) {
  let hash = 0;
  for (let index = 0; index < value.length; index += 1) hash = (hash * 31 + value.charCodeAt(index)) >>> 0;
  return hash;
}

function endpointId(endpoint: unknown) {
  if (typeof endpoint === 'string') return endpoint;
  if (endpoint && typeof endpoint === 'object' && 'id' in endpoint) return String(endpoint.id);
  return String(endpoint ?? '');
}

function drawRoundedRect(
  context: CanvasRenderingContext2D,
  x: number,
  y: number,
  width: number,
  height: number,
  radius: number,
) {
  context.beginPath();
  context.roundRect(x, y, width, height, radius);
}
