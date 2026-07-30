import { Activity } from 'lucide-react';
import { useMemo, useState } from 'react';
import type { OutlineVolume } from './outlinePresentation';
import {
  buildRhythmCurveModel,
  RHYTHM_INTENSITY_MAX,
  type OutlineBeatKey,
  type RhythmCurvePoint,
} from './rhythmCurveModel';

type Props = {
  activeVolumeIndex: number;
  onSelectBeat: (volumeIndex: number, beatKey: OutlineBeatKey) => void;
  volumes: OutlineVolume[];
};

const PLOT_TOP = 8;
const PLOT_HEIGHT = 78;
const AXIS_TICKS = [1, 2, 3, 4, 5];

/**
 * Outline 签名可视化：全书节奏折线（SVG 折线 + 可聚焦节拍点）。
 * 纵轴是叙事学五段结构的「结构预期强度」轮廓（见 rhythmCurveModel.ts），不是内容
 * 质量评分；卷 rhythm 原文只出现在读出行/aria-label。Beat Board 是等价表格。
 * 数据变化时仅做一次进入补间（--duration-standard 220ms，Reduced Motion 下为 0s）。
 */
export function RhythmCurve({ activeVolumeIndex, onSelectBeat, volumes }: Props) {
  const model = useMemo(() => buildRhythmCurveModel(volumes), [volumes]);
  const [readout, setReadout] = useState<RhythmCurvePoint | null>(null);
  const signature = useMemo(() => model.points.map((point) => `${point.volumeIndex}:${point.beatKey}`).join('|'), [model]);
  if (model.empty) {
    return (
      <section aria-label="全书节奏折线" className="rhythm-curve signature-chart">
        <p className="rhythm-curve-empty">暂无分卷数据，生成分卷大纲后展示全书节奏折线。</p>
      </section>
    );
  }
  const activeSpan = model.volumeSpans[activeVolumeIndex] ?? null;
  return (
    <section aria-label="全书节奏折线（结构预期强度）" className="rhythm-curve signature-chart">
      <header className="rhythm-curve-head">
        <span><Activity size={14} />全书节奏折线</span>
        <em>纵轴为五段结构的「结构预期强度」轮廓（1–5，结构语义，非内容质量评分）</em>
      </header>
      <div className="rhythm-curve-plot signature-chart-enter" key={signature}>
        <svg aria-hidden="true" className="rhythm-curve-canvas" preserveAspectRatio="none" viewBox="0 0 100 100">
          {activeSpan ? (
            <rect
              className="rhythm-curve-active-band"
              height="100"
              width={(activeSpan.endFraction - activeSpan.startFraction) * 100}
              x={activeSpan.startFraction * 100}
              y="0"
            />
          ) : null}
          {AXIS_TICKS.map((tick) => (
            <line className="rhythm-curve-grid" key={tick} vectorEffect="non-scaling-stroke" x1="0" x2="100" y1={yFor(tick)} y2={yFor(tick)} />
          ))}
          {model.boundaries.map((boundary) => (
            <line
              className="rhythm-curve-boundary"
              key={boundary.afterVolumeIndex}
              vectorEffect="non-scaling-stroke"
              x1={boundary.fraction * 100}
              x2={boundary.fraction * 100}
              y1="0"
              y2="100"
            />
          ))}
          <polyline
            className="rhythm-curve-line"
            points={model.points.map((point) => `${(point.xFraction * 100).toFixed(3)},${yFor(point.intensity).toFixed(3)}`).join(' ')}
            vectorEffect="non-scaling-stroke"
          />
        </svg>
        {AXIS_TICKS.map((tick) => (
          <span aria-hidden="true" className="rhythm-curve-axis" key={tick} style={{ top: `${yFor(tick)}%` }}>{tick}</span>
        ))}
        {model.points.map((point) => (
          <button
            aria-label={pointDescription(point)}
            className={`rhythm-curve-point${point.volumeIndex === activeVolumeIndex ? ' in-active-volume' : ''}`}
            key={point.order}
            onBlur={() => setReadout(null)}
            onClick={() => onSelectBeat(point.volumeIndex, point.beatKey)}
            onFocus={() => setReadout(point)}
            onMouseEnter={() => setReadout(point)}
            onMouseLeave={() => setReadout(null)}
            style={{ left: `${point.xFraction * 100}%`, top: `${yFor(point.intensity)}%` }}
            type="button"
          >
            <i aria-hidden="true" />
          </button>
        ))}
      </div>
      <div aria-hidden="true" className="rhythm-curve-volumes">
        {model.volumeSpans.map((span, index) => (
          <span className={index === activeVolumeIndex ? 'active' : ''} key={`${span.title}-${index}`} style={{ width: `${(span.endFraction - span.startFraction) * 100}%` }}>
            {span.title}
          </span>
        ))}
      </div>
      <p aria-live="polite" className="rhythm-curve-readout">
        {readout
          ? `${readout.volumeTitle} · ${readout.beatLabel}：结构预期 ${readout.intensity}/${RHYTHM_INTENSITY_MAX}${readout.rhythmText ? ` · 节奏原文：${readout.rhythmText}` : ''} · ${readout.beatText || '节拍待补全'}`
          : '悬停或聚焦节拍点查看结构预期与该卷节奏原文；点击定位下方节拍板对应列。'}
      </p>
    </section>
  );
}

function yFor(intensity: number) {
  return PLOT_TOP + (1 - intensity / RHYTHM_INTENSITY_MAX) * PLOT_HEIGHT;
}

function pointDescription(point: RhythmCurvePoint) {
  return `${point.volumeTitle} ${point.beatLabel}：结构预期强度 ${point.intensity}/${RHYTHM_INTENSITY_MAX}（结构预期，非内容评分），${point.beatText || '节拍待补全'}`;
}
