import { TERM } from './terminology';
import type { StageType } from '../contracts';

const stageToRoute = {
  brief: 'brief',
  spine: 'spine',
  cast: 'cast',
  volumes: 'volumes',
  detail: 'detail',
  text: 'text',
  cover: 'cover',
  export: 'export',
} as const satisfies Record<StageType, string>;

const routeToStage = Object.fromEntries(Object.entries(stageToRoute).map(([stageId, segment]) => [segment, stageId]));

/** Canonical eight-stage order shared with the LangGraph production graph. */
export const canonicalStageOrder = Object.keys(stageToRoute) as StageType[];

/** Studio Shell (Phase 11.2): the multi-project library and the app's default landing route. */
export const studioRoute = '/studio';
export const historyRoute = '/history';
export const knowledgeRoute = '/knowledge';
export const settingsRoute = '/settings';
/** Studio-scoped global pages: cross-project knowledge overview and global AI service settings. */
export const studioKnowledgeRoute = '/studio/knowledge';
export const studioSettingsRoute = '/studio/settings';
export const studioTemplatesRoute = '/studio?view=templates';

/** Full-page editor for one workflow template (stage chain + per-stage models). */
export function studioWorkflowRoute(workflowId: string) {
  return `/studio/workflow/${encodeURIComponent(workflowId)}`;
}
/** Run monitor console: the fast-mode default run surface, toggleable in balanced mode. */
export const monitorRoute = '/monitor';

export function isStudioRoute(pathname: string) {
  const normalized = pathname.length > 1 ? pathname.replace(/\/+$/, '') : pathname;
  return normalized === studioRoute;
}

export function routeForStage(stageId: string) {
  const route = stageToRoute[stageId as StageType];
  if (!route) throw new Error(`Unknown production stage: ${stageId}`);
  return `/run/${route}`;
}

export function stageIdFromRoute(segment?: string) {
  if (!segment) return '';
  return routeToStage[segment] ?? '';
}

export function isRunRoute(pathname: string) {
  return pathname.startsWith('/run/');
}

export function isKnownStageRoute(segment?: string) {
  return Boolean(stageIdFromRoute(segment));
}

export type BibleSection = 'cast' | 'world' | 'foreshadow' | 'facts';

export const bibleSections: BibleSection[] = ['cast', 'world', 'foreshadow', 'facts'];

export const defaultBibleSection: BibleSection = 'cast';

export const bibleSectionMeta: Record<BibleSection, { label: string; detail: string }> = {
  cast: { label: '人物关系', detail: '人物档案与关系网大图' },
  world: { label: '世界观', detail: '锚点与硬规则清单' },
  foreshadow: { label: '伏笔账本', detail: '投放 / 推进 / 回收 / 延后' },
  facts: { label: TERM.canonFacts, detail: '正典事实与冲突状态' },
};

export function routeForBibleSection(section: BibleSection) {
  return `/bible/${section}`;
}

/** True for any /bible path, including unknown sections that should redirect to the default section. */
export function isBibleRoute(pathname: string) {
  const normalized = pathname.length > 1 ? pathname.replace(/\/+$/, '') : pathname;
  return normalized === '/bible' || normalized.startsWith('/bible/');
}

function bibleSectionFromSegment(segment?: string): BibleSection | null {
  return bibleSections.includes(segment as BibleSection) ? (segment as BibleSection) : null;
}

export type PipelineRoute =
  | { phase: 'studio'; stageId: '' }
  | { phase: 'studio-knowledge'; stageId: '' }
  | { phase: 'studio-settings'; stageId: '' }
  | { phase: 'studio-workflow'; stageId: ''; workflowId: string }
  | { phase: 'history'; stageId: '' }
  | { phase: 'knowledge'; stageId: '' }
  | { phase: 'settings'; stageId: '' }
  | { phase: 'monitor'; stageId: '' }
  | { phase: 'planning'; stageId: '' }
  | { phase: 'running'; stageId: string }
  | { phase: 'bible'; stageId: ''; bibleSection: BibleSection };

export type PipelinePhase = PipelineRoute['phase'];

export function pipelineRouteFromPath(pathname: string): PipelineRoute | null {
  const normalized = pathname.length > 1 ? pathname.replace(/\/+$/, '') : pathname;
  if (normalized === studioRoute) return { phase: 'studio', stageId: '' };
  if (normalized === studioKnowledgeRoute) return { phase: 'studio-knowledge', stageId: '' };
  if (normalized === studioSettingsRoute) return { phase: 'studio-settings', stageId: '' };
  const workflowMatch = /^\/studio\/workflow\/([^/]+)$/.exec(normalized);
  if (workflowMatch) return { phase: 'studio-workflow', stageId: '', workflowId: decodeURIComponent(workflowMatch[1]) };
  if (normalized === historyRoute) return { phase: 'history', stageId: '' };
  if (normalized === knowledgeRoute) return { phase: 'knowledge', stageId: '' };
  if (normalized === settingsRoute) return { phase: 'settings', stageId: '' };
  if (normalized === monitorRoute) return { phase: 'monitor', stageId: '' };
  if (normalized === '/planning') return { phase: 'planning', stageId: '' };
  const bibleMatch = /^\/bible\/([^/]+)$/.exec(normalized);
  if (bibleMatch) {
    const section = bibleSectionFromSegment(bibleMatch[1]);
    return section ? { bibleSection: section, phase: 'bible', stageId: '' } : null;
  }
  const match = /^\/run\/([^/]+)$/.exec(normalized);
  const stageId = stageIdFromRoute(match?.[1]);
  return stageId ? { phase: 'running', stageId } : null;
}
