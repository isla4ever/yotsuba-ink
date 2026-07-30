import { useMemo } from 'react';
import { buildArcSwimlaneModel, type ArcSwimlaneLane, type ArcSwimlaneStop } from './characterArcSwimlaneModel';
import type { SummaryArtifact } from './stageArtifacts';

type Props = {
  artifact: SummaryArtifact;
  identities: Array<{ name: string; identity: string }>;
  onOpenArc: (index: number) => void;
};

/**
 * Summary 签名可视化：人物弧泳道（SVG）。
 * 横轴 = act_structure 真实幕序列；泳道 = character_arcs；幕轨上方的三角刻度
 * 是 key_turns 的全书转折刻度。映射规则见 characterArcSwimlaneModel.ts 顶部注释。
 * 图下方的文字摘要是等价内容（可访问性合同）；点击人物名打开既有深化弹层。
 */
export function CharacterArcSwimlanes({ artifact, identities, onOpenArc }: Props) {
  const model = useMemo(() => buildArcSwimlaneModel(artifact), [artifact]);
  const signature = useMemo(
    () => model.lanes.map((lane) => lane.stops.map((stop) => `${stop.kind}:${stop.fraction.toFixed(3)}:${stop.missing ? 0 : 1}`).join(',')).join('|'),
    [model],
  );
  if (model.empty) {
    return <p className="summary-relationship-empty">暂无人物弧数据。生成梗概或在「深化」中补全 character_arcs 后展示泳道图。</p>;
  }
  const identityByName = new Map(identities.map((item) => [item.name, item.identity]));
  return (
    <div className="arc-swimlanes signature-chart signature-chart-enter" key={signature}>
      <div aria-label={`幕结构轨，共 ${model.acts.length} 幕`} className="arc-swimlane-acts" role="list">
        {model.actsMissing
          ? <span className="arc-swimlane-acts-missing">幕结构待补全，泳道仅按全书顺序排布</span>
          : model.acts.map((act, index) => (
            <span key={`${act.title}-${index}`} role="listitem" style={{ width: `${(act.endFraction - act.startFraction) * 100}%` }}>
              {act.title}
            </span>
          ))}
        {model.ticks.length ? (
          <svg aria-hidden="true" className="arc-swimlane-ticks" preserveAspectRatio="none" viewBox="0 0 100 10">
            {model.ticks.map((tick, index) => (
              <polygon
                className="arc-swimlane-tick"
                key={`${tick.label}-${index}`}
                points={`${(tick.fraction * 100).toFixed(2)},10 ${(tick.fraction * 100 - 1.1).toFixed(2)},0 ${(tick.fraction * 100 + 1.1).toFixed(2)},0`}
              >
                <title>{`全书转折 ${index + 1}：${tick.label}${tick.detail ? ` — ${tick.detail}` : ''}`}</title>
              </polygon>
            ))}
          </svg>
        ) : null}
      </div>
      <div className="arc-swimlane-rows">
        {model.lanes.map((lane) => (
          <div className="arc-swimlane-row" key={`${lane.name}-${lane.arcIndex}`}>
            <button
              aria-label={`打开 ${lane.name} 的人物深化`}
              className="arc-swimlane-name"
              onClick={() => onOpenArc(lane.arcIndex)}
              type="button"
            >
              <b>{lane.name}</b>
              <small>{identityByName.get(lane.name) ?? '身份待定'}</small>
            </button>
            <svg aria-label={laneDescription(lane)} className="arc-swimlane-track" role="img">
              {model.acts.slice(1).map((act, index) => (
                <line className="arc-swimlane-separator" key={`sep-${index}`} x1={`${act.startFraction * 100}%`} x2={`${act.startFraction * 100}%`} y1="0%" y2="100%" />
              ))}
              <line className="arc-swimlane-baseline" x1={`${trackX(0)}%`} x2={`${trackX(1)}%`} y1="50%" y2="50%" />
              {lane.stops.map((stop) => (
                <circle
                  className={`arc-swimlane-stop stop-${stop.kind}${stop.unassignedAct ? ' unassigned' : ''}${stop.missing ? ' missing' : ''}`}
                  cx={`${trackX(stop.fraction)}%`}
                  cy="50%"
                  key={stop.kind}
                  r="5"
                >
                  <title>{stopDescription(stop)}</title>
                </circle>
              ))}
            </svg>
          </div>
        ))}
      </div>
      <p className="arc-swimlane-legend">
        <span><i aria-hidden="true" className="key stop-start" />人物起点</span>
        <span><i aria-hidden="true" className="key stop-pressure" />关系压力</span>
        <span><i aria-hidden="true" className="key stop-end" />后续影响</span>
        <span><i aria-hidden="true" className="key tick" />全书转折刻度（详见关键转折栏）</span>
        {model.hasUnassignedPressure ? <span><i aria-hidden="true" className="key stop-pressure unassigned" />未指明幕次（压力原文未指明幕，置于中段）</span> : null}
      </p>
      <ul className="arc-swimlane-digest">
        {model.lanes.map((lane) => (
          <li key={`digest-${lane.name}-${lane.arcIndex}`}>
            <b>{lane.name}</b>
            {lane.stops.map((stop) => (
              <span key={stop.kind}>
                <em>{stopShortLabel(stop.kind)}</em>
                {stop.missing ? '待补' : stop.text}
                {stop.kind === 'pressure' && !stop.missing && stop.unassignedAct ? '（未指明幕次）' : ''}
              </span>
            ))}
          </li>
        ))}
      </ul>
    </div>
  );
}

/** 泳道内 4%–96% 的绘图带，给起点/终点标记留出半径空间。 */
function trackX(fraction: number) {
  return 4 + fraction * 92;
}

function stopShortLabel(kind: ArcSwimlaneStop['kind']) {
  if (kind === 'start') return '起';
  if (kind === 'pressure') return '压';
  return '终';
}

function stopDescription(stop: ArcSwimlaneStop) {
  const body = stop.missing ? '待补' : stop.text;
  const suffix = stop.kind === 'pressure' && !stop.missing && stop.unassignedAct ? '（未指明幕次）' : '';
  return `${stop.label}：${body}${suffix}`;
}

function laneDescription(lane: ArcSwimlaneLane) {
  return `${lane.name} 的人物弧：${lane.stops.map((stop) => stopDescription(stop)).join('；')}`;
}
