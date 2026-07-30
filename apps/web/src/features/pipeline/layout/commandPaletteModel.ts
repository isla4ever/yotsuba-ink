import { sidebarStageItems } from './workbenchSidebarModel';
import { bibleSectionMeta, bibleSections, type BibleSection } from '../lib/stageRoutes';
import type { StageRuntimeSummaryMap } from '../state/pipelineShellContext';
import type { ModeRoutePolicy } from '../state/runPresentationState';
import type { QualityMode, WorkflowStage } from '../contracts';

export type PaletteGroupId = 'navigation' | 'global' | 'appearance';

export type PaletteCommand = {
  id: string;
  title: string;
  group: PaletteGroupId;
  keywords: string[];
  detail: string;
  disabled: boolean;
  disabledReason: string;
  closesPalette: boolean;
};

export type PaletteContext = {
  stages: Array<Pick<WorkflowStage, 'id' | 'label'>>;
  /** Phase 12 F5: low-frequency per-stage runtime summary from the shell slice. */
  stageRuntimes: StageRuntimeSummaryMap;
  policy: ModeRoutePolicy;
  qualityMode: QualityMode;
  runHasStarted: boolean;
  theme: 'dark' | 'light';
  sidebarExpanded: boolean;
};

export const paletteGroupLabels: Record<PaletteGroupId, string> = {
  navigation: '导航',
  global: '全局',
  appearance: '外观',
};

export const paletteStageCommandPrefix = 'stage:';

export const paletteBibleCommandPrefix = 'bible:';

export function bibleSectionFromCommandId(commandId: string): BibleSection | null {
  const section = commandId.slice(paletteBibleCommandPrefix.length) as BibleSection;
  return bibleSections.includes(section) ? section : null;
}

function command(
  id: string,
  group: PaletteGroupId,
  title: string,
  detail: string,
  keywords: string[],
  closesPalette: boolean,
): PaletteCommand {
  return { closesPalette, detail, disabled: false, disabledReason: '', group, id, keywords, title };
}

export function buildPaletteCommands(context: PaletteContext): PaletteCommand[] {
  const stageCommands = sidebarStageItems({
    policy: context.policy,
    qualityMode: context.qualityMode,
    runHasStarted: context.runHasStarted,
    stageRuntimes: context.stageRuntimes,
    stages: context.stages,
  }).map<PaletteCommand>((item) => ({
    closesPalette: true,
    detail: item.statusLabel,
    disabled: item.disabled,
    disabledReason: item.disabledReason,
    group: 'navigation',
    id: `${paletteStageCommandPrefix}${item.id}`,
    keywords: [item.label, item.id, '阶段', '跳转', 'stage'],
    title: `跳转到${item.label}`,
  }));
  const bibleCommands = bibleSections.map((section) => {
    const meta = bibleSectionMeta[section];
    return command(
      `${paletteBibleCommandPrefix}${section}`,
      'navigation',
      `打开 Story Bible · ${meta.label}`,
      `只读浏览 · ${meta.detail}`,
      [meta.label, section, 'story bible', 'bible', '设定集'],
      true,
    );
  });
  const darkTheme = context.theme === 'dark';
  return [
    ...stageCommands,
    command('nav:planning', 'navigation', '打开创作规划', '配置工作流与启动创作', ['规划', '工作流', '配置', 'planning'], true),
    command('nav:studio', 'navigation', '返回工作室', '浏览全部作品与工作流模板', ['工作室', '作品库', '返回', 'studio', 'library'], true),
    ...bibleCommands,
    command('studio:new-project', 'global', '新建作品', '打开新建作品向导（书名 + 模板）', ['新建', '作品', '小说', 'new', 'project'], true),
    command('open:knowledge', 'global', '打开知识资料', '管理项目资料与检索依据', ['知识', '资料', '知识库', '文档', '检索', 'knowledge'], true),
    command('open:history', 'global', '打开创作历史', '查看运行、快照与导出版本', ['历史', '运行', '快照', '导出', 'history'], true),
    command('open:settings', 'global', '打开模型与设置', '编辑服务、模型和工作流偏好', ['设置', 'provider', '模型', '服务', '偏好', 'settings'], true),
    command(
      'appearance:theme',
      'appearance',
      darkTheme ? '切换到日间主题' : '切换到夜间主题',
      '在明暗主题之间切换',
      ['主题', '日间', '夜间', '明暗', 'theme', 'dark', 'light'],
      false,
    ),
    command(
      'appearance:sidebar',
      'appearance',
      context.sidebarExpanded ? '收起侧栏' : '展开侧栏',
      '调整工作台侧栏宽度偏好',
      ['侧栏', '侧边栏', '收起', '展开', 'sidebar'],
      false,
    ),
  ];
}

export function filterPaletteCommands(commands: PaletteCommand[], query: string): PaletteCommand[] {
  const needle = query.trim().toLowerCase();
  if (!needle) return commands;
  return commands.filter(
    (item) => item.title.toLowerCase().includes(needle) || item.keywords.some((keyword) => keyword.toLowerCase().includes(needle)),
  );
}

export function groupPaletteCommands(commands: PaletteCommand[]) {
  const order: PaletteGroupId[] = ['navigation', 'global', 'appearance'];
  return order
    .map((id) => ({ commands: commands.filter((item) => item.group === id), id, label: paletteGroupLabels[id] }))
    .filter((group) => group.commands.length > 0);
}

export function firstEnabledCommandId(commands: PaletteCommand[]): string {
  return commands.find((item) => !item.disabled)?.id ?? '';
}

export function movePaletteHighlight(commands: PaletteCommand[], currentId: string, direction: 1 | -1): string {
  const enabled = commands.filter((item) => !item.disabled);
  if (!enabled.length) return '';
  const index = enabled.findIndex((item) => item.id === currentId);
  if (index < 0) return direction === 1 ? enabled[0].id : enabled[enabled.length - 1].id;
  return enabled[(index + direction + enabled.length) % enabled.length].id;
}

export function isPaletteShortcut(event: { altKey: boolean; ctrlKey: boolean; key: string; metaKey: boolean }): boolean {
  return (event.metaKey || event.ctrlKey) && !event.altKey && event.key.toLowerCase() === 'k';
}

export function isEditableEventTarget(target: { isContentEditable?: boolean; tagName?: string } | null): boolean {
  if (!target) return false;
  if (target.isContentEditable) return true;
  const tag = (target.tagName ?? '').toUpperCase();
  return tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT';
}

export function paletteShortcutHint(navigatorLike: { platform?: string; userAgent?: string } | null): string {
  const signature = `${navigatorLike?.platform ?? ''} ${navigatorLike?.userAgent ?? ''}`;
  return /Mac|iPhone|iPad|iPod/i.test(signature) ? '⌘K' : 'Ctrl K';
}
