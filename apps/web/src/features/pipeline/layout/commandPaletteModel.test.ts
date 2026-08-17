import { describe, expect, it } from 'vitest';
import {
  buildPaletteCommands,
  filterPaletteCommands,
  firstEnabledCommandId,
  groupPaletteCommands,
  isEditableEventTarget,
  isPaletteShortcut,
  movePaletteHighlight,
  type PaletteContext,
} from './commandPaletteModel';
import { buildRunEventIndex } from '../state/runEventIndex';
import { modeRoutePolicy } from '../state/runPresentationState';
import { stageRuntimeSummaryMap } from '../state/useStageRuntimes';
import type { RunEvent } from '../contracts';
import { runEvent } from '../contracts/runEventTestFactory';

const stages = [
  { id: 'brief', label: '创作立项定稿', type: 'brief' as const },
  { id: 'spine', label: '故事脊柱', type: 'spine' as const },
  { id: 'text', label: '正文生成', type: 'text' as const },
];

function context(overrides: Partial<PaletteContext> = {}): PaletteContext {
  return {
    stageRuntimes: stageRuntimeSummaryMap(
      buildRunEventIndex([runEvent('artifact.committed', { run_id: 'run-1', stage_id: 'brief', node_id: 'brief.commit_artifact', payload: {} })]),
      stages,
    ),
    policy: modeRoutePolicy('deep'),
    qualityMode: 'deep',
    runHasStarted: true,
    sidebarExpanded: true,
    stages,
    theme: 'dark',
    ...overrides,
  };
}

describe('buildPaletteCommands', () => {
  it('derives stage commands with real status and keeps all balanced workbenches reachable', () => {
    const commands = buildPaletteCommands(context({ policy: modeRoutePolicy('balanced'), qualityMode: 'balanced' }));
    const brief = commands.find((command) => command.id === 'stage:brief');
    const spine = commands.find((command) => command.id === 'stage:spine');
    expect(brief?.disabled).toBe(false);
    expect(brief?.detail).toBe('已完成');
    expect(spine?.disabled).toBe(false);
    expect(spine?.disabledReason).toBe('');
  });

  it('exposes the Studio Shell commands 返回工作室 and 新建作品 (Phase 11.2)', () => {
    const commands = buildPaletteCommands(context());
    const studio = commands.find((command) => command.id === 'nav:studio');
    const newProject = commands.find((command) => command.id === 'studio:new-project');
    expect(studio?.title).toBe('返回工作室');
    expect(studio?.group).toBe('navigation');
    expect(studio?.disabled).toBe(false);
    expect(newProject?.title).toBe('新建作品');
    expect(newProject?.detail).toBe('选择流水线并提交一段创作想法');
    expect(newProject?.group).toBe('global');
    expect(filterPaletteCommands(commands, '工作室').map((command) => command.id)).toContain('nav:studio');
    expect(filterPaletteCommands(commands, '新建').map((command) => command.id)).toContain('studio:new-project');
  });

  it('flips theme and sidebar command titles from the current context', () => {
    const dark = buildPaletteCommands(context({ sidebarExpanded: true, theme: 'dark' }));
    expect(dark.find((command) => command.id === 'appearance:theme')?.title).toBe('切换到日间主题');
    expect(dark.find((command) => command.id === 'appearance:sidebar')?.title).toBe('收起侧栏');

    const light = buildPaletteCommands(context({ sidebarExpanded: false, theme: 'light' }));
    expect(light.find((command) => command.id === 'appearance:theme')?.title).toBe('切换到夜间主题');
    expect(light.find((command) => command.id === 'appearance:sidebar')?.title).toBe('展开侧栏');
  });
});

describe('filterPaletteCommands', () => {
  it('returns all commands grouped as 导航/全局/外观 for an empty query', () => {
    const commands = buildPaletteCommands(context());
    const groups = groupPaletteCommands(filterPaletteCommands(commands, '  '));
    expect(groups.map((group) => group.label)).toEqual(['导航', '全局', '外观']);
    expect(groups[0].commands).toHaveLength(9); // 3 stages + 当前工作台 + 返回工作室 + 4 Story Bible sections
    expect(groups.reduce((total, group) => total + group.commands.length, 0)).toBe(commands.length);
  });

  it('matches Chinese substrings and keyword aliases such as provider/模型 for settings', () => {
    const commands = buildPaletteCommands(context());
    for (const query of ['设置', 'provider', '模型', 'Provider']) {
      const hits = filterPaletteCommands(commands, query);
      expect(hits.some((command) => command.id === 'open:settings'), `query=${query}`).toBe(true);
    }
    expect(filterPaletteCommands(commands, '历史').map((command) => command.id)).toEqual(['open:history']);
    expect(filterPaletteCommands(commands, '不存在的命令')).toHaveLength(0);
  });

  it('exposes the four Story Bible navigation commands and matches bible queries', () => {
    const commands = buildPaletteCommands(context());
    const bibleIds = commands.filter((command) => command.id.startsWith('bible:')).map((command) => command.id);
    expect(bibleIds).toEqual(['bible:cast', 'bible:world', 'bible:foreshadow', 'bible:facts']);
    expect(filterPaletteCommands(commands, 'bible').map((command) => command.id)).toEqual(bibleIds);
    expect(filterPaletteCommands(commands, '伏笔').some((command) => command.id === 'bible:foreshadow')).toBe(true);
    for (const command of commands.filter((item) => item.id.startsWith('bible:'))) {
      expect(command.disabled).toBe(false);
    }
  });

  it('keeps pre-run navigation focused on creative preparation', () => {
    const commands = buildPaletteCommands(context({ runHasStarted: false }));
    expect(commands.find((command) => command.id === 'nav:planning')?.title).toBe('打开创作准备');
    expect(commands.some((command) => command.id.startsWith('stage:'))).toBe(false);
    expect(commands.some((command) => command.id.startsWith('bible:'))).toBe(false);
  });
});

describe('movePaletteHighlight', () => {
  it('skips disabled commands and wraps around in both directions', () => {
    const commands = buildPaletteCommands(context({ policy: modeRoutePolicy('balanced'), qualityMode: 'balanced' }));
    const enabledIds = commands.filter((command) => !command.disabled).map((command) => command.id);
    expect(firstEnabledCommandId(commands)).toBe(enabledIds[0]);
    expect(movePaletteHighlight(commands, enabledIds[0], 1)).toBe(enabledIds[1]);
    expect(movePaletteHighlight(commands, enabledIds[0], -1)).toBe(enabledIds[enabledIds.length - 1]);
    expect(movePaletteHighlight(commands, enabledIds[enabledIds.length - 1], 1)).toBe(enabledIds[0]);
    expect(enabledIds).toContain('stage:spine');
  });
});

describe('shortcut boundaries', () => {
  it('accepts Cmd+K / Ctrl+K only, without Alt', () => {
    expect(isPaletteShortcut({ altKey: false, ctrlKey: false, key: 'k', metaKey: true })).toBe(true);
    expect(isPaletteShortcut({ altKey: false, ctrlKey: true, key: 'K', metaKey: false })).toBe(true);
    expect(isPaletteShortcut({ altKey: false, ctrlKey: false, key: 'k', metaKey: false })).toBe(false);
    expect(isPaletteShortcut({ altKey: true, ctrlKey: false, key: 'k', metaKey: true })).toBe(false);
    expect(isPaletteShortcut({ altKey: false, ctrlKey: true, key: 'j', metaKey: false })).toBe(false);
  });

  it('ignores keystrokes coming from inputs, textareas and contentEditable hosts', () => {
    expect(isEditableEventTarget({ tagName: 'INPUT' })).toBe(true);
    expect(isEditableEventTarget({ tagName: 'textarea' })).toBe(true);
    expect(isEditableEventTarget({ isContentEditable: true, tagName: 'DIV' })).toBe(true);
    expect(isEditableEventTarget({ tagName: 'BUTTON' })).toBe(false);
    expect(isEditableEventTarget(null)).toBe(false);
  });
});
