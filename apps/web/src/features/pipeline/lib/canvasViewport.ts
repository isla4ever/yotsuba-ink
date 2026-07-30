import type { Node } from '@xyflow/react';

export function canvasFitPadding(width: number, height: number) {
  const base = Math.max(0.04, Math.min(0.1, 78 / Math.max(width, 1)));
  if (height < 560) return Math.max(base, 0.08);
  return base;
}

export function shouldAutoCenterCanvas(nodes: Node[]) {
  return nodes.length > 0;
}
