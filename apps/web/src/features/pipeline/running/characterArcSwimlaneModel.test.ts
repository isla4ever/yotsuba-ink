import { describe, expect, it } from 'vitest';
import { buildArcSwimlaneModel } from './characterArcSwimlaneModel';

const acts = [
  { goal: '建立悬念', title: '觉醒', turn: '发现母带' },
  { goal: '证据咬合', title: '对峙', turn: '同盟破裂' },
  { goal: '收束因果', title: '清算', turn: '真相公开' },
];

const arc = (name: string, pressure?: string, next?: string) => ({
  arc: `${name}从旁观走向下场`,
  name,
  next,
  pressure,
});

describe('character arc swimlane mapping', () => {
  it('maps key_turns in narrative order onto the act track as whole-book ticks', () => {
    const model = buildArcSwimlaneModel({
      act_structure: acts,
      character_arcs: [arc('林拾', '压力', '后续')],
      key_turns: [
        { detail: 'a', label: '转折一' },
        { detail: 'b', label: '转折二' },
        { detail: 'c', label: '转折三' },
        { detail: 'd', label: '转折四' },
      ],
    });
    expect(model.ticks.map((tick) => tick.fraction)).toEqual([0.125, 0.375, 0.625, 0.875]);
    expect(model.ticks.map((tick) => tick.actIndex)).toEqual([0, 1, 1, 2]);
  });

  it('assigns the pressure stop to the unique act named in its text', () => {
    const model = buildArcSwimlaneModel({
      act_structure: acts,
      character_arcs: [arc('林拾', '在对峙中与旧同盟决裂', '接管清算')],
      key_turns: [],
    });
    const pressure = model.lanes[0].stops[1];
    expect(pressure.actIndex).toBe(1);
    expect(pressure.fraction).toBeCloseTo(0.5);
    expect(pressure.unassignedAct).toBe(false);
    expect(model.hasUnassignedPressure).toBe(false);
  });

  it('keeps a pressure without act attribution at mid-book and flags it as unassigned', () => {
    const model = buildArcSwimlaneModel({
      act_structure: acts,
      character_arcs: [arc('林拾', '与旧同盟决裂', '接管残局')],
      key_turns: [],
    });
    const pressure = model.lanes[0].stops[1];
    expect(pressure.fraction).toBe(0.5);
    expect(pressure.actIndex).toBeNull();
    expect(pressure.unassignedAct).toBe(true);
    expect(model.hasUnassignedPressure).toBe(true);
  });

  it('treats a pressure that names multiple acts as unassigned instead of guessing', () => {
    const model = buildArcSwimlaneModel({
      act_structure: acts,
      character_arcs: [arc('林拾', '从觉醒一路拖进清算', '离场')],
      key_turns: [],
    });
    expect(model.lanes[0].stops[1].unassignedAct).toBe(true);
    expect(model.lanes[0].stops[1].actIndex).toBeNull();
  });

  it('reports the empty state and marks missing fields without fabricating data', () => {
    expect(buildArcSwimlaneModel({ act_structure: acts, character_arcs: [], key_turns: [] }).empty).toBe(true);
    const model = buildArcSwimlaneModel({
      act_structure: [],
      character_arcs: [{ arc: '', name: '阿岚' }],
      key_turns: [],
    });
    expect(model.actsMissing).toBe(true);
    const [start, pressure, end] = model.lanes[0].stops;
    expect(start.missing).toBe(true);
    expect(pressure.missing).toBe(true);
    expect(end.missing).toBe(true);
    // 缺失的压力不算「未指明幕次」——它是待补，不是已存在但无法归属。
    expect(model.hasUnassignedPressure).toBe(false);
  });
});
