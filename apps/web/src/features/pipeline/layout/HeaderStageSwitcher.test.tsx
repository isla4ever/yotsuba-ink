// @vitest-environment happy-dom

import { act } from 'react';
import { createRoot, type Root } from 'react-dom/client';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { HeaderStageSwitcher } from './HeaderStageSwitcher';
import type { SidebarStageItem } from './workbenchSidebarModel';

(globalThis as Record<string, unknown>).IS_REACT_ACT_ENVIRONMENT = true;

const items: SidebarStageItem[] = [
  { id: 'info', label: '小说信息', status: 'done', statusLabel: '已完成', disabled: false, disabledReason: '' },
  { id: 'summary', label: '全书梗概', status: 'running', statusLabel: '进行中', disabled: false, disabledReason: '' },
  { id: 'outline', label: '分卷大纲', status: 'idle', statusLabel: '未开始', disabled: true, disabledReason: '尚未解锁' },
];

describe('HeaderStageSwitcher', () => {
  let container: HTMLDivElement;
  let root: Root;

  beforeEach(() => {
    container = document.createElement('div');
    document.body.appendChild(container);
    root = createRoot(container);
  });

  afterEach(() => {
    act(() => root.unmount());
    container.remove();
  });

  it('shows stage order, status, current value, and disabled state', () => {
    act(() => root.render(<HeaderStageSwitcher currentStageId="summary" items={items} onNavigate={() => undefined} />));

    const select = container.querySelector<HTMLSelectElement>('select[aria-label="切换创作阶段"]');
    const options = Array.from(select?.options ?? []);
    expect(select?.value).toBe('summary');
    expect(options.map((option) => option.textContent)).toEqual([
      '01 小说信息 · 已完成',
      '02 全书梗概 · 进行中',
      '03 分卷大纲 · 未开始',
    ]);
    expect(options[2]?.disabled).toBe(true);
  });

  it('navigates through the selected stage id', () => {
    const onNavigate = vi.fn();
    act(() => root.render(<HeaderStageSwitcher currentStageId="info" items={items} onNavigate={onNavigate} />));

    const select = container.querySelector<HTMLSelectElement>('select');
    expect(select).not.toBeNull();
    act(() => {
      if (!select) return;
      select.value = 'summary';
      select.dispatchEvent(new Event('change', { bubbles: true }));
    });

    expect(onNavigate).toHaveBeenCalledOnce();
    expect(onNavigate).toHaveBeenCalledWith('summary');
  });
});
