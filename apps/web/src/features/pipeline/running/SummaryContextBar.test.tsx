import { renderToStaticMarkup } from 'react-dom/server';
import { describe, expect, it } from 'vitest';
import { SummaryContextBar } from './SummaryContextBar';

describe('SummaryContextBar', () => {
  it('exposes the contract progress and the exact missing artifact field', () => {
    const html = renderToStaticMarkup(
      <SummaryContextBar
        generating={false}
        onOneLinerChange={() => undefined}
        oneLiner="一盘母带重新打开旧案。"
        readOnly={false}
        readiness={{ completed: 7, missingLabels: ['人物弧'], ready: false, total: 8 }}
      />,
    );

    expect(html).toContain('aria-label="内容完整度 7/8"');
    expect(html).toContain('待补：人物弧');
    expect(html.match(/class="complete"/g)).toHaveLength(7);
  });

  it('describes a complete Summary as ready for the outline decision', () => {
    const html = renderToStaticMarkup(
      <SummaryContextBar
        generating={false}
        onOneLinerChange={() => undefined}
        oneLiner="一盘母带重新打开旧案。"
        readOnly
        readiness={{ completed: 8, missingLabels: [], ready: true, total: 8 }}
      />,
    );

    expect(html).toContain('可作为分卷依据');
    expect(html).toContain('readonly=""');
  });
});
