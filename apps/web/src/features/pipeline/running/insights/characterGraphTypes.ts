import type { CharacterEdgeHistoryEntry, CharacterNode, RelationKind, RelationPolarity } from '../../contracts';

export type GraphNode = CharacterNode & {
  val: number;
  color: string;
  initialX: number;
  initialY: number;
  x?: number;
  y?: number;
  vx?: number;
  vy?: number;
  fx?: number;
  fy?: number;
};

export type GraphEndpoint = string | GraphNode;

export type GraphLink = {
  source: GraphEndpoint;
  target: GraphEndpoint;
  relation: string;
  strength: number;
  kind?: RelationKind;
  polarity?: RelationPolarity;
  history?: CharacterEdgeHistoryEntry[];
};
