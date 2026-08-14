import { describe, expect, it } from 'vitest';
import { canonicalStageOrder, isBibleRoute, isStudioRoute, pipelineRouteFromPath, routeForBibleSection } from './stageRoutes';

describe('pipelineRouteFromPath', () => {
  it('resolves the Studio Shell route with or without a trailing slash (Phase 11.2)', () => {
    expect(pipelineRouteFromPath('/studio')).toEqual({ phase: 'studio', stageId: '' });
    expect(pipelineRouteFromPath('/studio/')).toEqual({ phase: 'studio', stageId: '' });
    expect(pipelineRouteFromPath('/studio/nested')).toBeNull();
    expect(isStudioRoute('/studio')).toBe(true);
    expect(isStudioRoute('/studios')).toBe(false);
    expect(canonicalStageOrder).toEqual(['brief', 'spine', 'cast', 'volumes', 'detail', 'text', 'cover', 'export']);
  });

  it('resolves planning with or without a trailing slash', () => {
    expect(pipelineRouteFromPath('/planning')).toEqual({ phase: 'planning', stageId: '' });
    expect(pipelineRouteFromPath('/planning/')).toEqual({ phase: 'planning', stageId: '' });
  });

  it('resolves the full-page creation history route', () => {
    expect(pipelineRouteFromPath('/history')).toEqual({ phase: 'history', stageId: '' });
    expect(pipelineRouteFromPath('/history/')).toEqual({ phase: 'history', stageId: '' });
  });

  it('resolves known stage routes', () => {
    expect(pipelineRouteFromPath('/run/brief')).toEqual({ phase: 'running', stageId: 'brief' });
    expect(pipelineRouteFromPath('/run/cast')).toEqual({ phase: 'running', stageId: 'cast' });
    expect(pipelineRouteFromPath('/run/export/')).toEqual({ phase: 'running', stageId: 'export' });
  });

  it('rejects unknown and nested routes', () => {
    expect(pipelineRouteFromPath('/')).toBeNull();
    expect(pipelineRouteFromPath('/run/unknown')).toBeNull();
    expect(pipelineRouteFromPath('/run/brief/nested')).toBeNull();
    expect(pipelineRouteFromPath('/run/info')).toBeNull();
    expect(pipelineRouteFromPath('/run/characters')).toBeNull();
  });

  it('resolves the four Story Bible sections', () => {
    expect(pipelineRouteFromPath('/bible/cast')).toEqual({ bibleSection: 'cast', phase: 'bible', stageId: '' });
    expect(pipelineRouteFromPath('/bible/world/')).toEqual({ bibleSection: 'world', phase: 'bible', stageId: '' });
    expect(pipelineRouteFromPath('/bible/foreshadow')).toEqual({ bibleSection: 'foreshadow', phase: 'bible', stageId: '' });
    expect(pipelineRouteFromPath('/bible/facts')).toEqual({ bibleSection: 'facts', phase: 'bible', stageId: '' });
  });

  it('marks unknown bible sections for redirect instead of resolving them', () => {
    expect(pipelineRouteFromPath('/bible/unknown')).toBeNull();
    expect(pipelineRouteFromPath('/bible')).toBeNull();
    expect(pipelineRouteFromPath('/bible/cast/nested')).toBeNull();
    expect(pipelineRouteFromPath('/bible/characters')).toBeNull();
    expect(isBibleRoute('/bible/unknown')).toBe(true);
    expect(isBibleRoute('/bible')).toBe(true);
    expect(isBibleRoute('/bibles')).toBe(false);
    expect(isBibleRoute('/run/brief')).toBe(false);
    expect(routeForBibleSection('cast')).toBe('/bible/cast');
  });
});
