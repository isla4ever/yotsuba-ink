import { HeartPulse } from 'lucide-react';
import { useMemo, useState } from 'react';
import type { RunEvent } from '../contracts';
import {
  buildTensionSeries,
  TENSION_MAX,
  tensionPointDescription,
  type TensionPoint,
} from './tensionTrackModel';
import type { WritingChapter } from './writingArtifactModel';

type Props = {
  activeChapterId: string;
  chapters: WritingChapter[];
  events: RunEvent[];
  locked: boolean;
  onSelectChapter: (chapterId: string) => void;
};

const PLOT_TOP = 6;
const PLOT_HEIGHT = 82;
const AXIS_TICKS = [0, 5, 10];

/**
 * Text 签名可视化：全书张力心电图（Phase 10.3c，SVG 折线 + 数据点，无扫描线等装饰动画）。
 * 纵轴为章后模型评审产出的真实张力分（story_bible.tension_track，0-10）；
 * 无分数章节画缺口断线（不插值——插值是伪造）。点击章节点走既有切章入口
 * （含处理中锁定与脏态保护）。数据变化仅一次 220ms 进入补间。
 */
export function TensionCurve({ activeChapterId, chapters, events, locked, onSelectChapter }: Props) {
  const series = useMemo(() => buildTensionSeries(chapters, events, activeChapterId), [activeChapterId, chapters, events]);
  const [readout, setReadout] = useState<TensionPoint | null>(null);
  if (series.empty) {
    return (
      <section aria-label="全书张力心电" className="tension-curve signature-chart empty">
        <p className="tension-curve-missing"><HeartPulse size={13} />张力评分在平衡/精细档的章后评审生成，当前运行暂无张力数据。</p>
      </section>
    );
  }
  const signature = series.points.map((point) => `${point.chapterId}:${point.score ?? 'x'}`).join('|');
  const bandWidth = 100 / Math.max(1, series.points.length);
  const current = series.points.find((point) => point.isCurrent) ?? null;
  return (
    <section aria-label="全书张力心电（章后模型评审真实分数）" className="tension-curve signature-chart">
      <header className="tension-curve-head">
        <span><HeartPulse size={14} />全书张力心电</span>
        <em>纵轴为章后模型评审的张力分（0–10）；缺分章节留缺口，不插值</em>
      </header>
      <div className="tension-curve-plot signature-chart-enter" key={signature}>
        <svg aria-hidden="true" className="tension-curve-canvas" preserveAspectRatio="none" viewBox="0 0 100 100">
          {current ? (
            <rect className="tension-curve-current-band" height="100" width={bandWidth} x={current.xFraction * 100 - bandWidth / 2} y="0" />
          ) : null}
          {AXIS_TICKS.map((tick) => (
            <line className="tension-curve-grid" key={tick} vectorEffect="non-scaling-stroke" x1="0" x2="100" y1={yFor(tick)} y2={yFor(tick)} />
          ))}
          {series.segments.filter((segment) => segment.length > 1).map((segment) => (
            <polyline
              className="tension-curve-line"
              key={segment[0].index}
              points={segment.map((point) => `${(point.xFraction * 100).toFixed(3)},${yFor(point.score ?? 0).toFixed(3)}`).join(' ')}
              vectorEffect="non-scaling-stroke"
            />
          ))}
        </svg>
        {AXIS_TICKS.map((tick) => (
          <span aria-hidden="true" className="tension-curve-axis" key={tick} style={{ top: `${yFor(tick)}%` }}>{tick}</span>
        ))}
        {series.points.map((point) => (
          <button
            aria-current={point.isCurrent ? 'true' : undefined}
            aria-label={tensionPointDescription(point)}
            className={`tension-curve-point${point.isCurrent ? ' current' : ''}${point.score == null ? ' unscored' : ''}`}
            disabled={locked && !point.isCurrent}
            key={point.chapterId}
            onBlur={() => setReadout(null)}
            onClick={() => onSelectChapter(point.chapterId)}
            onFocus={() => setReadout(point)}
            onMouseEnter={() => setReadout(point)}
            onMouseLeave={() => setReadout(null)}
            style={{ left: `${point.xFraction * 100}%`, top: point.score == null ? undefined : `${yFor(point.score)}%` }}
            type="button"
          >
            <i aria-hidden="true" />
          </button>
        ))}
      </div>
      <p aria-live="polite" className="tension-curve-readout">
        {readout
          ? tensionPointDescription(readout)
          : `已评分 ${series.scoredCount}/${series.points.length} 章 · 悬停或聚焦章节点查看评分依据；点击切换到该章。`}
      </p>
    </section>
  );
}

function yFor(score: number) {
  return PLOT_TOP + (1 - score / TENSION_MAX) * PLOT_HEIGHT;
}
