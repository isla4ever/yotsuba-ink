import { TERM } from './terminology';

const stageToRoute: Record<string, string> = {
  info: 'info',
  summary: 'summary',
  outline: 'outline',
  detail: 'detail',
  text: 'text',
  cover: 'cover',
  export: 'export',
};

const routeToStage = Object.fromEntries(Object.entries(stageToRoute).map(([stageId, segment]) => [segment, stageId]));

/** Canonical seven-stage order (used by Studio progress dots and stage derivations). */
export const canonicalStageOrder = Object.keys(stageToRoute);

/** Studio Shell (Phase 11.2): the multi-project library and the app's default landing route. */
export const studioRoute = '/studio';
export const historyRoute = '/history';

export function isStudioRoute(pathname: string) {
  const normalized = pathname.length > 1 ? pathname.replace(/\/+$/, '') : pathname;
  return normalized === studioRoute;
}

export function routeForStage(stageId: string) {
  return `/run/${stageToRoute[stageId] ?? stageId}`;
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

export type BibleSection = 'characters' | 'world' | 'foreshadow' | 'facts';

export const bibleSections: BibleSection[] = ['characters', 'world', 'foreshadow', 'facts'];

export const defaultBibleSection: BibleSection = 'characters';

export const bibleSectionMeta: Record<BibleSection, { label: string; detail: string }> = {
  characters: { label: '人物关系', detail: '人物档案与关系网大图' },
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
  | { phase: 'history'; stageId: '' }
  | { phase: 'planning'; stageId: '' }
  | { phase: 'running'; stageId: string }
  | { phase: 'bible'; stageId: ''; bibleSection: BibleSection };

export function pipelineRouteFromPath(pathname: string): PipelineRoute | null {
  const normalized = pathname.length > 1 ? pathname.replace(/\/+$/, '') : pathname;
  if (normalized === studioRoute) return { phase: 'studio', stageId: '' };
  if (normalized === historyRoute) return { phase: 'history', stageId: '' };
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
