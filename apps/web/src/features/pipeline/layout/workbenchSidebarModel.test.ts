import { describe, expect, it } from 'vitest';
import {
  defaultSidebarExpanded,
  loadSidebarExpanded,
  saveSidebarExpanded,
  sidebarExpandedStorageKey,
  sidebarStageItems,
  type SidebarPreferenceStorage,
} from './workbenchSidebarModel';
import { buildRunEventIndex } from '../state/runEventIndex';
import { modeRoutePolicy } from '../state/runPresentationState';
import { stageRuntimeSummaryMap } from '../state/useStageRuntimes';
import type { RunEvent } from '../contracts';

const stages = [
  { id: 'info', label: '创作立项定稿', type: 'info_recommend' as const },
  { id: 'summary', label: '梗概定稿', type: 'summary' as const },
  { id: 'text', label: '正文生成', type: 'chapter_text' as const },
];

function event(type: string, nodeId: string): RunEvent {
  return { type, node_id: nodeId } as RunEvent;
}

function runtimesFrom(events: RunEvent[]) {
  return stageRuntimeSummaryMap(buildRunEventIndex(events), stages);
}

describe('sidebarStageItems route policy', () => {
  it('disables every stage in fast mode and explains the cockpit takeover', () => {
    const items = sidebarStageItems({
      policy: modeRoutePolicy('fast', false),
      qualityMode: 'fast',
      runHasStarted: true,
      stageRuntimes: {},
      stages,
    });
    expect(items.every((item) => item.disabled)).toBe(true);
    expect(items[0].disabledReason).toBe('极速模式下阶段进度在驾驶舱内查看');
  });

  it('keeps only the info stage reachable in balanced mode', () => {
    const items = sidebarStageItems({
      policy: modeRoutePolicy('balanced', false),
      qualityMode: 'balanced',
      runHasStarted: true,
      stageRuntimes: {},
      stages,
    });
    expect(items.find((item) => item.id === 'info')?.disabled).toBe(false);
    const summary = items.find((item) => item.id === 'summary');
    expect(summary?.disabled).toBe(true);
    expect(summary?.disabledReason).toBe('平衡模式下后续阶段在驾驶舱内查看');
  });

  it('disables deep-mode stages before the run starts and frees them after', () => {
    const policy = modeRoutePolicy('deep', false);
    const before = sidebarStageItems({ policy, qualityMode: 'deep', runHasStarted: false, stageRuntimes: {}, stages });
    expect(before.every((item) => item.disabled)).toBe(true);
    expect(before[0].disabledReason).toBe('启动创作后可进入阶段工作台');

    const after = sidebarStageItems({ policy, qualityMode: 'deep', runHasStarted: true, stageRuntimes: {}, stages });
    expect(after.every((item) => !item.disabled)).toBe(true);
  });
});

describe('sidebarStageItems status derivation', () => {
  it('derives real stage status from run events instead of faking progress', () => {
    const events = [
      event('node_started', 'summary'),
      event('node_completed', 'info'),
      event('node_started', 'info'),
    ];
    const items = sidebarStageItems({
      policy: modeRoutePolicy('deep', false),
      qualityMode: 'deep',
      runHasStarted: true,
      stageRuntimes: runtimesFrom(events),
      stages,
    });
    expect(items.map((item) => item.status)).toEqual(['done', 'running', 'idle']);
    expect(items.map((item) => item.statusLabel)).toEqual(['已完成', '进行中', '未开始']);
  });

  it('labels a lifecycle-complete Cover without an image asset as 待完善', () => {
    const coverStages = [{ id: 'cover', label: 'AI 封面', type: 'cover_image' as const }];
    const events = [{
      type: 'node_completed',
      run_id: 'run-1',
      node_id: 'cover',
      result: { brief: '简报', prompt: 'prompt', candidates: [{ id: 'cover-1', image_url: '' }], selected_candidate_id: 'cover-1' },
    }] as RunEvent[];
    const items = sidebarStageItems({
      policy: modeRoutePolicy('deep', false),
      qualityMode: 'deep',
      runHasStarted: true,
      stageRuntimes: stageRuntimeSummaryMap(buildRunEventIndex(events), coverStages),
      stages: coverStages,
    });
    expect(items[0]).toMatchObject({ status: 'attention', statusLabel: '待完善' });
  });
});

describe('sidebar expand preference', () => {
  it('persists the manual preference and prefers it over the viewport default', () => {
    const storage = memoryStorage();
    expect(loadSidebarExpanded(true, storage)).toBe(true);

    saveSidebarExpanded(false, storage);
    expect(storage.getItem(sidebarExpandedStorageKey)).toBe('collapsed');
    expect(loadSidebarExpanded(true, storage)).toBe(false);

    saveSidebarExpanded(true, storage);
    expect(loadSidebarExpanded(false, storage)).toBe(true);
  });

  it('defaults to expanded only on wide viewports (>=1280px)', () => {
    expect(defaultSidebarExpanded(true)).toBe(true);
    expect(defaultSidebarExpanded(false)).toBe(false);
  });
});

function memoryStorage(): SidebarPreferenceStorage {
  const values = new Map<string, string>();
  return {
    getItem: (key) => values.get(key) ?? null,
    setItem: (key, value) => {
      values.set(key, value);
    },
  };
}
