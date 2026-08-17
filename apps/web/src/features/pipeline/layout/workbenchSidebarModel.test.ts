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
import { runEvent } from '../contracts/runEventTestFactory';

const stages = [
  { id: 'brief', label: '创作立项定稿', type: 'brief' as const },
  { id: 'spine', label: '梗概定稿', type: 'spine' as const },
  { id: 'text', label: '正文生成', type: 'text' as const },
];

function event(type: string, nodeId: string): RunEvent {
  return runEvent(type, { run_id: 'run-1', stage_id: nodeId as RunEvent['stage_id'], node_id: `${nodeId}.generate_candidate` });
}

function runtimesFrom(events: RunEvent[]) {
  return stageRuntimeSummaryMap(buildRunEventIndex(events), stages);
}

describe('sidebarStageItems route policy', () => {
  it('disables every stage in fast mode and points to the creation console', () => {
    const items = sidebarStageItems({
      policy: modeRoutePolicy('fast'),
      qualityMode: 'fast',
      runHasStarted: true,
      stageRuntimes: {},
      stages,
    });
    expect(items.every((item) => item.disabled)).toBe(true);
    expect(items[0].disabledReason).toBe('极速模式下阶段进度在创作控制台查看');
  });

  it('keeps every stage workbench reachable in balanced mode', () => {
    const items = sidebarStageItems({
      policy: modeRoutePolicy('balanced'),
      qualityMode: 'balanced',
      runHasStarted: true,
      stageRuntimes: {},
      stages,
    });
    expect(items.every((item) => !item.disabled)).toBe(true);
  });

  it('disables deep-mode stages before the run starts and frees them after', () => {
    const policy = modeRoutePolicy('deep');
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
      event('node.started', 'spine'),
      { ...event('artifact.committed', 'brief'), payload: {}, node_id: 'brief.commit_artifact' },
      event('node.started', 'brief'),
    ];
    const items = sidebarStageItems({
      policy: modeRoutePolicy('deep'),
      qualityMode: 'deep',
      runHasStarted: true,
      stageRuntimes: runtimesFrom(events),
      stages,
    });
    expect(items.map((item) => item.status)).toEqual(['done', 'running', 'idle']);
    expect(items.map((item) => item.statusLabel)).toEqual(['已完成', '进行中', '未开始']);
  });

  it('labels a lifecycle-complete Cover without an image asset as 待完善', () => {
    const coverStages = [{ id: 'cover', label: 'AI 封面', type: 'cover' as const }];
    const events = [runEvent('artifact.committed', {
      run_id: 'run-1',
      stage_id: 'cover',
      node_id: 'cover.commit_artifact',
      payload: {
        brief: { concept: '简报', image_prompt: '雾港剪影', palette: ['#111827'], negative_constraints: [] },
        selected_asset_id: '',
      },
    })];
    const items = sidebarStageItems({
      policy: modeRoutePolicy('deep'),
      qualityMode: 'deep',
      runHasStarted: true,
      stageRuntimes: stageRuntimeSummaryMap(buildRunEventIndex(events), coverStages),
      stages: coverStages,
    });
    expect(items[0]).toMatchObject({ status: 'attention', statusLabel: '待完善' });
  });

  it('labels a LangGraph human interrupt as 待决策', () => {
    const items = sidebarStageItems({
      policy: modeRoutePolicy('deep'),
      qualityMode: 'deep',
      runHasStarted: true,
      stageRuntimes: runtimesFrom([event('decision.required', 'spine')]),
      stages,
    });
    expect(items[1]).toMatchObject({ status: 'awaiting', statusLabel: '待决策' });
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
