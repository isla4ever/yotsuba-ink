import type { SummaryArtifact } from './stageArtifacts';

/**
 * Phase 10.3a 人物弧泳道映射规则（纯函数，全部值可指回真实产物字段）：
 *
 * 1. 横轴是 act_structure 的真实幕序列，等宽排布。合同没有幕时长/篇幅数据，
 *    等宽只表达“顺序结构”，不虚构任何篇幅比例。
 * 2. key_turns 是全书级转折，合同不含幕归属字段。第 i 个（共 n 个）转折按
 *    叙事顺序落在 fraction=(i+0.5)/n 的位置，归属幕 = 该 fraction 所落入的
 *    等宽幕区间。它只作为幕轨上方的“全书转折刻度”，不进入任何人物泳道，
 *    不伪造“某人物在某幕发生某转折”的幕级明细。
 * 3. character_arcs 是整体字段（arc/pressure/next），合同里不按幕拆分。
 *    泳道只画三个真实锚点：arc（起点，fraction 0）→ pressure（中段标注）→
 *    next（终点，fraction 1）。pressure 的幕归属仅当其原文恰好包含唯一一个
 *    幕标题（去空格后长度 >= 2）时成立；包含 0 个或多个幕标题时置于全书
 *    中段 fraction 0.5，并标记 unassignedAct（UI 显示「未指明幕次」）。
 */

export type ArcSwimlaneStopKind = 'start' | 'pressure' | 'end';

export type ArcSwimlaneStop = {
  actIndex: number | null;
  fraction: number;
  kind: ArcSwimlaneStopKind;
  label: string;
  missing: boolean;
  text: string;
  unassignedAct: boolean;
};

export type ArcSwimlaneAct = {
  endFraction: number;
  startFraction: number;
  title: string;
};

export type ArcSwimlaneTick = {
  actIndex: number | null;
  detail: string;
  fraction: number;
  label: string;
};

export type ArcSwimlaneLane = {
  arcIndex: number;
  name: string;
  stops: ArcSwimlaneStop[];
};

export type ArcSwimlaneModel = {
  acts: ArcSwimlaneAct[];
  actsMissing: boolean;
  empty: boolean;
  hasUnassignedPressure: boolean;
  lanes: ArcSwimlaneLane[];
  ticks: ArcSwimlaneTick[];
};

type SwimlaneSource = Pick<SummaryArtifact, 'act_structure' | 'character_arcs' | 'key_turns'>;

export function actIndexAtFraction(fraction: number, actCount: number): number | null {
  if (actCount <= 0) return null;
  return Math.max(0, Math.min(actCount - 1, Math.floor(fraction * actCount)));
}

function pressureStop(pressure: string, actTitles: string[]): Pick<ArcSwimlaneStop, 'actIndex' | 'fraction' | 'unassignedAct'> {
  const trimmed = pressure.trim();
  const matches = actTitles
    .map((title, index) => ({ index, title: title.trim() }))
    .filter(({ title }) => title.length >= 2 && trimmed.includes(title));
  if (trimmed && matches.length === 1) {
    const actIndex = matches[0].index;
    return { actIndex, fraction: (actIndex + 0.5) / actTitles.length, unassignedAct: false };
  }
  return { actIndex: null, fraction: 0.5, unassignedAct: true };
}

export function buildArcSwimlaneModel(source: SwimlaneSource): ArcSwimlaneModel {
  const actCount = source.act_structure.length;
  const acts: ArcSwimlaneAct[] = source.act_structure.map((act, index) => ({
    endFraction: (index + 1) / actCount,
    startFraction: index / actCount,
    title: act.title.trim() || `第${index + 1}幕`,
  }));
  const actTitles = source.act_structure.map((act) => act.title);
  const turnCount = source.key_turns.length;
  const ticks: ArcSwimlaneTick[] = source.key_turns.map((turn, index) => {
    const fraction = (index + 0.5) / turnCount;
    return {
      actIndex: actIndexAtFraction(fraction, actCount),
      detail: turn.detail,
      fraction,
      label: turn.label.trim() || `转折 ${index + 1}`,
    };
  });
  const lanes: ArcSwimlaneLane[] = source.character_arcs.map((arc, arcIndex) => {
    const pressure = arc.pressure ?? '';
    const next = arc.next ?? '';
    const assigned = pressureStop(pressure, actTitles);
    return {
      arcIndex,
      name: arc.name.trim() || `角色 ${arcIndex + 1}`,
      stops: [
        {
          actIndex: actIndexAtFraction(0, actCount),
          fraction: 0,
          kind: 'start',
          label: '人物起点',
          missing: !arc.arc.trim(),
          text: arc.arc,
          unassignedAct: false,
        },
        {
          ...assigned,
          kind: 'pressure',
          label: '关系压力',
          missing: !pressure.trim(),
          text: pressure,
        },
        {
          actIndex: actIndexAtFraction(0.999, actCount),
          fraction: 1,
          kind: 'end',
          label: '后续影响',
          missing: !next.trim(),
          text: next,
          unassignedAct: false,
        },
      ],
    };
  });
  return {
    acts,
    actsMissing: actCount === 0,
    empty: lanes.length === 0,
    hasUnassignedPressure: lanes.some((lane) => lane.stops.some((stop) => stop.kind === 'pressure' && stop.unassignedAct && !stop.missing)),
    lanes,
    ticks,
  };
}
