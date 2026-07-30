import { renderToStaticMarkup } from 'react-dom/server';
import { describe, expect, it } from 'vitest';
import { CharacterArcSwimlanes } from './CharacterArcSwimlanes';
import { summaryArtifact } from './stageArtifacts';

const artifact = (value: Record<string, unknown>) => summaryArtifact(JSON.stringify(value));

describe('CharacterArcSwimlanes', () => {
  it('falls back to the existing empty-state semantics when no character arcs exist', () => {
    const html = renderToStaticMarkup(
      <CharacterArcSwimlanes artifact={artifact({})} identities={[]} onOpenArc={() => undefined} />,
    );
    expect(html).toContain('summary-relationship-empty');
    expect(html).toContain('暂无人物弧数据');
    expect(html).not.toContain('arc-swimlane-track');
  });

  it('renders one lane per arc plus the equivalent text digest and the unassigned-act note', () => {
    const html = renderToStaticMarkup(
      <CharacterArcSwimlanes
        artifact={artifact({
          act_structure: [
            { goal: 'a', title: '觉醒', turn: 't1' },
            { goal: 'b', title: '对峙', turn: 't2' },
            { goal: 'c', title: '清算', turn: 't3' },
          ],
          character_arcs: [
            { arc: '从旁观到下场', name: '林拾', next: '接管清算', pressure: '与旧同盟决裂' },
          ],
          key_turns: [{ detail: '母带出现', label: '开场翻转' }],
        })}
        identities={[{ identity: '殡仪馆整音师', name: '林拾' }]}
        onOpenArc={() => undefined}
      />,
    );
    expect(html.match(/arc-swimlane-track/g)).toHaveLength(1);
    expect(html).toContain('aria-label="打开 林拾 的人物深化"');
    expect(html).toContain('殡仪馆整音师');
    expect(html).toContain('全书转折 1：开场翻转');
    // 压力原文未指明幕次 → 中段标注 + 图例与摘要中的诚实说明。
    expect(html).toContain('未指明幕次');
    expect(html).toContain('arc-swimlane-digest');
    expect(html).toContain('接管清算');
  });
});
