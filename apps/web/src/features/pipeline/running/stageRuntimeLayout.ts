import type { StageType } from '../contracts';

export type RuntimePanelKey = 'character' | 'knowledge' | 'worldbuilding' | 'wiki' | 'quality' | 'contextManifest' | 'coverQuality' | 'exportSummary';

export type StageRuntimeLayout = Readonly<{
  primary: readonly RuntimePanelKey[];
  compact: readonly RuntimePanelKey[];
}>;

export const stageRuntimeLayout = {
  brief: {
    primary: [],
    compact: [],
  },
  spine: {
    primary: [],
    compact: ['worldbuilding', 'quality'],
  },
  cast: {
    primary: [],
    compact: [],
  },
  volumes: {
    primary: [],
    compact: ['character', 'worldbuilding', 'quality'],
  },
  detail: {
    primary: [],
    compact: ['character', 'worldbuilding', 'quality'],
  },
  text: {
    primary: [],
    compact: ['contextManifest', 'quality', 'wiki', 'character', 'worldbuilding'],
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
