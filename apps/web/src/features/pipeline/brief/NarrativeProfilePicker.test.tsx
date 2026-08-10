import { renderToStaticMarkup } from 'react-dom/server';
import { describe, expect, it } from 'vitest';
import { NarrativeProfilePicker } from './NarrativeProfilePicker';

describe('NarrativeProfilePicker', () => {
  it('shows all roles and keeps the selected prompt inspectable but read-only', () => {
    const html = renderToStaticMarkup(<NarrativeProfilePicker value="悬念导演" onChange={() => undefined} />);
    expect(html).toContain('role="radiogroup"');
    expect(html).toContain('aria-checked="true"');
    expect(html).toContain('查看完整角色 Prompt');
    expect(html).toContain('精于证据链、信息差与可回溯反转的类型小说导演');
    expect(html).toContain('职责：控制读者知道什么、误判什么，并让揭示重新照亮前文证据。');
    expect(html).toContain('阶段 Artifact、Canon、人物知识边界、SceneContract');
    expect(html.match(/tabindex="0"/g)).toHaveLength(1);
    expect(html.match(/tabindex="-1"/g)).toHaveLength(5);
    expect(html).not.toContain('textarea');
    expect(html.match(/role="radio"/g)).toHaveLength(6);
  });
});
