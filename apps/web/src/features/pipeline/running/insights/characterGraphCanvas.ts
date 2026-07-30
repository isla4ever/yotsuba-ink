import type { CharacterGraph } from '../../contracts';
import type { GraphEndpoint, GraphLink, GraphNode } from './characterGraphTypes';

export function drawCharacterNode(node: GraphNode, ctx: CanvasRenderingContext2D, globalScale: number, hovered: boolean) {
  const label = node.name.slice(0, 1);
  const radius = (node.val + 1.8) * (hovered ? 1.18 : 1);
  const x = node.x ?? 0;
  const y = node.y ?? 0;
  const innerColor = softenColor(node.color);
  ctx.beginPath();
  ctx.arc(x, y, radius + 3.2, 0, 2 * Math.PI, false);
  ctx.fillStyle = `${node.color}2e`;
  ctx.fill();
  ctx.beginPath();
  ctx.arc(x, y, radius + 5.4, 0, 2 * Math.PI, false);
  ctx.strokeStyle = `${node.color}${hovered ? '88' : '36'}`;
  ctx.lineWidth = hovered ? 1.4 : 0.8;
  ctx.stroke();
  ctx.beginPath();
  ctx.arc(x, y, radius, 0, 2 * Math.PI, false);
  ctx.fillStyle = innerColor;
  ctx.fill();
  ctx.strokeStyle = node.color;
  ctx.lineWidth = 1.3;
  ctx.stroke();
  const fontSize = Math.max(6.8, Math.min(radius * 1.08, 9.2 / globalScale));
  ctx.font = `700 ${fontSize}px Inter, sans-serif`;
  ctx.textAlign = 'center';
  ctx.textBaseline = 'middle';
  ctx.fillStyle = textColorFor(innerColor);
  ctx.fillText(label, x, y);
}

export function drawRelationLayer(link: GraphLink, ctx: CanvasRenderingContext2D, globalScale: number, hovered: boolean) {
  drawRelationGlow(link, ctx, hovered);
  drawRelationLabel(link, ctx, globalScale, hovered);
}

export function linkKey(link: GraphLink) {
  return `${idForEndpoint(link.source)}-${idForEndpoint(link.target)}-${link.relation}`;
}

export function idForEndpoint(endpoint: GraphEndpoint) {
  return typeof endpoint === 'string' ? endpoint : endpoint.id;
}

export function nameFor(graph: CharacterGraph, id: string) {
  return graph.nodes.find((node) => node.id === id)?.name ?? id;
}

export function graphFitPadding(width: number, height: number) {
  const shortSide = Math.min(width, height);
  return Math.max(28, Math.min(54, shortSide * 0.1));
}

function drawRelationGlow(link: GraphLink, ctx: CanvasRenderingContext2D, hovered: boolean) {
  const source = link.source as GraphNode;
  const target = link.target as GraphNode;
  if (typeof link.source === 'string' || typeof link.target === 'string') return;
  const startX = source.x ?? 0;
  const startY = source.y ?? 0;
  const endX = target.x ?? 0;
  const endY = target.y ?? 0;
  const x = startX + (endX - startX) * 0.58;
  const y = startY + (endY - startY) * 0.58;
  ctx.save();
  ctx.beginPath();
  ctx.arc(x, y, hovered ? 2.4 : 1.6, 0, 2 * Math.PI, false);
  ctx.fillStyle = hovered ? getCssVar('--accent-2') : pointColor();
  ctx.shadowColor = getCssVar('--accent-2');
  ctx.shadowBlur = hovered ? 10 : 5;
  ctx.fill();
  ctx.restore();
}

function drawRelationLabel(link: GraphLink, ctx: CanvasRenderingContext2D, globalScale: number, hovered: boolean) {
  const source = link.source as GraphNode;
  const target = link.target as GraphNode;
  if (typeof link.source === 'string' || typeof link.target === 'string') return;
  const x = ((source.x ?? 0) + (target.x ?? 0)) / 2;
  const y = ((source.y ?? 0) + (target.y ?? 0)) / 2;
  if (!hovered && globalScale < 0.78 && link.strength < 0.66) return;
  const fontSize = hovered ? Math.max(5, 5.8 / globalScale) : Math.max(4.2, 5 / globalScale);
  ctx.font = `700 ${fontSize}px Inter, sans-serif`;
  const width = ctx.measureText(link.relation).width + 6;
  ctx.fillStyle = hovered ? getCssVar('--graph-label-bg-strong') : getCssVar('--graph-label-bg');
  roundRect(ctx, x - width / 2, y - fontSize / 2 - 2, width, fontSize + 4, 4);
  ctx.fill();
  ctx.fillStyle = getCssVar('--graph-label-text') || getCssVar('--text-soft');
  ctx.textAlign = 'center';
  ctx.textBaseline = 'middle';
  ctx.fillText(link.relation, x, y);
}

function roundRect(ctx: CanvasRenderingContext2D, x: number, y: number, width: number, height: number, radius: number) {
  ctx.beginPath();
  ctx.moveTo(x + radius, y);
  ctx.arcTo(x + width, y, x + width, y + height, radius);
  ctx.arcTo(x + width, y + height, x, y + height, radius);
  ctx.arcTo(x, y + height, x, y, radius);
  ctx.arcTo(x, y, x + radius, y, radius);
  ctx.closePath();
}

export function getCssVar(name: string) {
  return getComputedStyle(document.documentElement).getPropertyValue(name).trim();
}

function softenColor(hex: string) {
  const { r, g, b } = hexToRgb(hex);
  const mixBase = document.documentElement.dataset.theme === 'light' ? 236 : 255;
  const mixRatio = document.documentElement.dataset.theme === 'light' ? 0.28 : 0.18;
  const mix = (value: number) => Math.round(value * (1 - mixRatio) + mixBase * mixRatio);
  return rgbToHex(mix(r), mix(g), mix(b));
}

function textColorFor(hex: string) {
  const { r, g, b } = hexToRgb(hex);
  const luminance = 0.2126 * channel(r) + 0.7152 * channel(g) + 0.0722 * channel(b);
  return luminance > 0.56 ? '#14304f' : '#f8fbff';
}

function pointColor() {
  return document.documentElement.dataset.theme === 'light' ? 'rgba(90, 112, 148, 0.68)' : 'rgba(255,255,255,0.58)';
}

function channel(value: number) {
  const normalized = value / 255;
  return normalized <= 0.03928 ? normalized / 12.92 : ((normalized + 0.055) / 1.055) ** 2.4;
}

function hexToRgb(hex: string) {
  const clean = hex.replace('#', '');
  const value = Number.parseInt(clean.length === 3 ? clean.split('').map((char) => `${char}${char}`).join('') : clean, 16);
  return {
    r: (value >> 16) & 255,
    g: (value >> 8) & 255,
    b: value & 255,
  };
}

function rgbToHex(r: number, g: number, b: number) {
  return `#${[r, g, b].map((value) => value.toString(16).padStart(2, '0')).join('')}`;
}
