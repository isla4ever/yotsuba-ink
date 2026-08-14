import { describe, expect, it } from 'vitest';
import { defaultWorkflow } from '../state/defaultWorkflow';
import {
  buildEdges,
  buildNodes,
  isCanvasNodeActivationKey,
  isCanvasViewportInteractive,
} from './pipelineCanvasGraph';

describe('pipeline canvas interaction contract', () => {
  it('maps the standard button keys to node activation', () => {
    expect(isCanvasNodeActivationKey('Enter')).toBe(true);
    expect(isCanvasNodeActivationKey(' ')).toBe(true);
    expect(isCanvasNodeActivationKey('Spacebar')).toBe(false);
    expect(isCanvasNodeActivationKey('ArrowRight')).toBe(false);
  });

  it('allows viewport manipulation only when both locks are clear', () => {
    expect(isCanvasViewportInteractive(false, false)).toBe(true);
    expect(isCanvasViewportInteractive(true, false)).toBe(false);
    expect(isCanvasViewportInteractive(false, true)).toBe(false);
    expect(isCanvasViewportInteractive(true, true)).toBe(false);
  });
});

describe('cockpit runtime layer availability', () => {
  it('exposes planning stages as named keyboard actions', () => {
    const nodes = buildNodes(defaultWorkflow, 'brief', [], false, 'planning', false);
    const info = nodes.find((node) => node.id === 'brief');
    const spine = nodes.find((node) => node.id === 'spine');

    expect(info).toMatchObject({ ariaRole: 'button', focusable: true, selectable: true, selected: true });
    expect(info?.ariaLabel).toContain('第 1 阶段，创作立项定稿');
    expect(info?.ariaLabel).toContain('当前选中');
    expect(spine?.ariaLabel).toContain('第 2 阶段，故事脊柱');
  });

  it('marks Wiki and quality nodes unavailable before a run starts', () => {
    const nodes = buildNodes(defaultWorkflow, 'brief', [], true, 'cockpit-vertical', false);
    const runtimeNodes = nodes.filter((node) => node.id === 'wiki-layer' || node.id === 'quality-layer');
    const info = nodes.find((node) => node.id === 'brief');

    expect(info?.ariaLabel).toContain('打开阶段设置');
    expect(runtimeNodes).toHaveLength(2);
    runtimeNodes.forEach((node) => {
      expect(node).toMatchObject({ ariaRole: 'group', draggable: false, focusable: false, selectable: false });
      expect(node.ariaLabel).toContain('启动创作后可用');
      expect(node.data).toMatchObject({ disabled: true, selected: false, subtitle: '启动后可用' });
    });
    expect(buildEdges(defaultWorkflow, [], 'brief', true, 'cockpit-vertical', false)
      .filter((edge) => edge.id.startsWith('wiki-') || edge.id.startsWith('quality-'))
      .every((edge) => edge.className?.includes('disabled'))).toBe(true);
  });

  it('restores runtime layer interaction after the run starts', () => {
    const nodes = buildNodes(defaultWorkflow, 'wiki-layer', [], true, 'cockpit-vertical', true);
    const wiki = nodes.find((node) => node.id === 'wiki-layer');
    const info = nodes.find((node) => node.id === 'brief');

    expect(info?.ariaLabel).toContain('打开只读阶段快照');
    expect(wiki).toMatchObject({ ariaRole: 'button', draggable: true, focusable: true, selectable: true });
    expect(wiki?.ariaLabel).toBe('Wiki 事实层，打开事实读写详情');
    expect(wiki?.data).toMatchObject({ disabled: false, selected: true, subtitle: '读写约束' });
  });
});
