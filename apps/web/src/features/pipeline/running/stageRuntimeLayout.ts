import type { StageType } from '../contracts';

export type RuntimePanelKey = 'character' | 'knowledge' | 'worldbuilding' | 'wiki' | 'quality' | 'coverQuality' | 'exportSummary';

export type StageRuntimeLayout = Readonly<{
  primary: readonly RuntimePanelKey[];
  compact: readonly RuntimePanelKey[];
}>;

export const stageRuntimeLayout = {
  info_recommend: {
    primary: [],
    compact: [],
  },
  summary: {
    primary: [],
    compact: ['character', 'worldbuilding', 'quality'],
  },
  outline: {
    primary: [],
    compact: ['character', 'worldbuilding', 'quality'],
  },
  detail_outline: {
    primary: [],
    compact: ['character', 'worldbuilding', 'wiki', 'quality'],
  },
  chapter_text: {
    primary: [],
    compact: [],
  },
  cover_image: {
    primary: [],
    compact: [],
  },
  export_artifact: {
    primary: [],
    compact: [],
  },
} as const satisfies Record<StageType, StageRuntimeLayout>;
