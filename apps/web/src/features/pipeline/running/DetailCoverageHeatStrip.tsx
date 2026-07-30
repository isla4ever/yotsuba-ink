import { LayoutGrid } from 'lucide-react';
import { useMemo, useState } from 'react';
import type { DetailBaseline } from './detailArtifactModel';
import { buildCoverageCells, coverageCellDescription, coverageSummary, type CoverageCell } from './detailCoverageModel';
import type { DetailChapter } from './detailPresentation';

type Props = {
  baseline: DetailBaseline;
  chapters: DetailChapter[];
  legacyFinalized?: boolean;
  onSelectChapter: (index: number) => void;
  selectedChapterIndex: number;
};

/**
 * Detail 签名可视化：章节覆盖热力条（Phase 10.3b）。
 * 横向每格 = 一章，色阶 = 该章五组检查（施工蓝图/人物变化/事实揭示/Wiki 候选/伏笔动作）
 * 的真实完成数 0-5，与施工表徽标同源（detailChapterReadiness）。五档 sequential 色阶
 * 经 dataviz 调色板校验器按 --ordinal 在两种主题表面验证通过。点击格子复用既有章节选中。
 */
export function DetailCoverageHeatStrip({ baseline, chapters, legacyFinalized = false, onSelectChapter, selectedChapterIndex }: Props) {
  const cells = useMemo(() => buildCoverageCells(chapters, baseline), [baseline, chapters]);
  const [readout, setReadout] = useState<CoverageCell | null>(null);
  if (!cells.length) {
    return (
      <section aria-label="章节覆盖热力条" className="coverage-heat-strip signature-chart">
        <p className="coverage-heat-missing">暂无章节施工数据，生成章节细纲后展示覆盖热力条。</p>
      </section>
    );
  }
  const signature = cells.map((cell) => `${cell.label}:${cell.completed}`).join('|');
  return (
    <section aria-label="章节覆盖热力条（每章五组检查完成数）" className="coverage-heat-strip signature-chart">
      <header className="coverage-heat-head">
        <span><LayoutGrid size={14} />覆盖热力条</span>
        <em>{coverageSummary(cells, legacyFinalized)}</em>
      </header>
      <div className="coverage-heat-cells signature-chart-enter" key={signature}>
        {cells.map((cell) => (
          <button
            aria-label={coverageCellDescription(cell, legacyFinalized)}
            aria-pressed={cell.index === selectedChapterIndex}
            className={cell.index === selectedChapterIndex ? 'selected' : ''}
            data-level={cell.completed}
            key={`${cell.label}-${cell.index}`}
            onBlur={() => setReadout(null)}
            onClick={() => onSelectChapter(cell.index)}
            onFocus={() => setReadout(cell)}
            onMouseEnter={() => setReadout(cell)}
            onMouseLeave={() => setReadout(null)}
            type="button"
          >
            <i aria-hidden="true" data-level={cell.completed} />
          </button>
        ))}
      </div>
      <div aria-hidden="true" className="coverage-heat-legend">
        <span>完成 0</span>
        {[1, 2, 3, 4, 5].map((level) => <i data-level={level} key={level} />)}
        <span>5</span>
      </div>
      <p aria-live="polite" className="coverage-heat-readout">
        {readout ? coverageCellDescription(readout, legacyFinalized) : legacyFinalized ? '历史稿按旧合同完成；色阶只表示新版结构字段覆盖。' : '悬停或聚焦格子查看该章缺口；点击选中对应章节。'}
      </p>
    </section>
  );
}
