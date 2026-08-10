import type { CharacterNode } from '../../contracts';

export type SpatialNode = CharacterNode & {
  val: number;
  x?: number;
  y?: number;
  z?: number;
  vx?: number;
  vy?: number;
  vz?: number;
  anchorX?: number;
  anchorY?: number;
  anchorZ?: number;
};

type SpatialPosition = Pick<SpatialNode, 'x' | 'y' | 'z' | 'anchorX' | 'anchorY' | 'anchorZ'>;
export type SpatialLayoutMode = 'landscape' | 'portrait';

export type NetworkCameraFrame = {
  distance: number;
  target: { x: number; y: number; z: number };
};

const goldenAngle = 2.399963229728653;

export function initialSpatialLayout(nodes: CharacterNode[], mode: SpatialLayoutMode = 'landscape'): SpatialPosition[] {
  const protagonistCount = nodes.filter((node) => node.tier === 'protagonist').length;
  const scaleX = mode === 'portrait' ? 0.56 : 1;
  const scaleY = mode === 'portrait' ? 1.16 : 1;
  const scaleZ = mode === 'portrait' ? 0.58 : 1;
  let protagonistIndex = 0;
  let peripheralIndex = 0;

  return nodes.map((node) => {
    if (node.tier === 'protagonist') {
      const angle = protagonistIndex * goldenAngle - Math.PI / 2;
      const radius = protagonistCount > 1 ? 48 : 0;
      protagonistIndex += 1;
      return anchoredPosition(
        Math.cos(angle) * radius * scaleX,
        Math.sin(angle) * radius * scaleY,
        (protagonistCount > 1 ? (protagonistIndex % 2 ? 18 : -18) : 0) * scaleZ,
      );
    }

    const ring = Math.floor(peripheralIndex / 8);
    const angle = peripheralIndex * goldenAngle - Math.PI / 2;
    const x = Math.cos(angle) * (188 + ring * 104);
    const y = Math.sin(angle) * (142 + ring * 78);
    const z = Math.sin(angle * 1.7) * 70 + ((peripheralIndex % 3) - 1) * 16;
    peripheralIndex += 1;
    return anchoredPosition(x * scaleX, y * scaleY, z * scaleZ);
  });
}

function anchoredPosition(x: number, y: number, z: number): SpatialPosition {
  const normalizedX = normalizeZero(x);
  const normalizedY = normalizeZero(y);
  const normalizedZ = normalizeZero(z);
  return {
    anchorX: normalizedX,
    anchorY: normalizedY,
    anchorZ: normalizedZ,
    x: normalizedX,
    y: normalizedY,
    z: normalizedZ,
  };
}

function normalizeZero(value: number) {
  return Math.abs(value) < 1e-9 ? 0 : value;
}

export function createSpatialAnchorForce(nodes: SpatialNode[]) {
  return (alpha: number) => {
    nodes.forEach((node) => {
      node.vx = (node.vx ?? 0) + ((node.anchorX ?? 0) - (node.x ?? 0)) * alpha * 0.105;
      node.vy = (node.vy ?? 0) + ((node.anchorY ?? 0) - (node.y ?? 0)) * alpha * 0.105;
      node.vz = (node.vz ?? 0) + ((node.anchorZ ?? 0) - (node.z ?? 0)) * alpha * 0.08;
    });
  };
}

export function networkCameraFrame(nodes: SpatialNode[], width: number, height: number): NetworkCameraFrame {
  const positioned = nodes.filter((node) => Number.isFinite(node.x) && Number.isFinite(node.y) && Number.isFinite(node.z));
  const xs = positioned.map((node) => node.x ?? 0);
  const ys = positioned.map((node) => node.y ?? 0);
  const zs = positioned.map((node) => node.z ?? 0);
  const target = {
    x: midpoint(xs),
    y: midpoint(ys),
    z: midpoint(zs),
  };
  const aspect = Math.max(0.5, width / Math.max(1, height));
  const tangent = Math.tan((75 * Math.PI) / 360);
  const labelPadding = width < 520 ? 126 : 108;
  const horizontal = Math.max(112, ...positioned.map((node) => Math.abs((node.x ?? 0) - target.x) + labelPadding));
  const vertical = Math.max(92, ...positioned.map((node) => Math.abs((node.y ?? 0) - target.y) + 92));
  const depth = Math.max(0, ...positioned.map((node) => Math.abs((node.z ?? 0) - target.z)));
  const fitHorizontal = horizontal / (tangent * aspect);
  const fitVertical = vertical / tangent;
  return {
    distance: Math.max(244, Math.round(Math.max(fitHorizontal, fitVertical) * 1.12 + depth + 30)),
    target,
  };
}

export function networkCameraDistance(nodes: SpatialNode[], width: number, height: number) {
  return networkCameraFrame(nodes, width, height).distance;
}

export function networkCameraBounds(fitDistance: number) {
  return {
    maximum: Math.max(420, fitDistance * 2.4),
    minimum: Math.max(132, fitDistance * 0.52),
  };
}

function midpoint(values: number[]) {
  if (!values.length) return 0;
  return (Math.min(...values) + Math.max(...values)) / 2;
}
