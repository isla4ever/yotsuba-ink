import type { StageType } from '../contracts';

export type RuntimePanelKey = 'character' | 'knowledge' | 'worldbuilding' | 'wiki' | 'quality' | 'coverQuality' | 'exportSummary';

export type StageRuntimeLayout = Readonly<{
  primary: readonly RuntimePanelKey[];
  compact: readonly RuntimePanelKey[];
}>;

export const stageRuntimeLayout = {
  info: {
    primary: [],
    compact: [],
  },
  characters: {
    primary: [],
    compact: ['character'],
  },
  summary: {
    primary: [],
    compact: ['character', 'worldbuilding', 'quality'],
  },
  outline: {
    primary: [],
    compact: ['character', 'worldbuilding', 'quality'],
  },
  detail: {
    primary: [],
    compact: ['character', 'worldbuilding', 'quality'],
  },
  text: {
    primary: [],
    compact: ['quality', 'wiki', 'character', 'worldbuilding'],
  },
  cover: {
    primary: [],
    compact: [],
  },
  export: {
    primary: [],
    compact: [],
  },
} as const satisfies Record<StageType, StageRuntimeLayout>;
