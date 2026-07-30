import { describe, expect, it } from 'vitest';
import type { OutlineVolume } from './outlinePresentation';
import { buildRhythmCurveModel, RHYTHM_EXPECTED_INTENSITY } from './rhythmCurveModel';

const volume = (title: string, overrides: Partial<OutlineVolume> = {}): OutlineVolume => ({
  chapter_range: '1-10',
  character_progression: [],
  climax: '高潮内容',
  development: '发展内容',
  foreshadow_plan: [],
  midpoint: '中点内容',
  opening: '开端内容',
  resolution: '结局内容',
  title,
  volume_goal: '卷目标',
  world_reveal: [],
  ...overrides,
});

describe('rhythm curve model', () => {
  it('lays out multi-volume beats continuously with a boundary at each volume edge', () => {
    const model = buildRhythmCurveModel([volume('卷一'), volume('卷二')]);
    expect(model.points).toHaveLength(10);
    expect(model.points.map((point) => point.order)).toEqual([0, 1, 2, 3, 4, 5, 6, 7, 8, 9]);
    const fractions = model.points.map((point) => point.xFraction);
    expect([...fractions].sort((a, b) => a - b)).toEqual(fractions);
    expect(model.points[0].xFraction).toBeCloseTo(0.05);
    expect(model.points[9].xFraction).toBeCloseTo(0.95);
    expect(model.boundaries).toEqual([{ afterVolumeIndex: 0, fraction: 0.5 }]);
    expect(model.volumeSpans.map((span) => [span.startFraction, span.endFraction])).toEqual([[0, 0.5], [0.5, 1]]);
  });

  it('renders a single volume without boundaries', () => {
    const model = buildRhythmCurveModel([volume('全一卷')]);
    expect(model.points).toHaveLength(5);
    expect(model.boundaries).toEqual([]);
    expect(model.points[2].xFraction).toBeCloseTo(0.5);
    expect(model.empty).toBe(false);
  });

  it('derives intensity only from the fixed five-beat structural profile, never from rhythm text', () => {
    const calm = buildRhythmCurveModel([volume('卷一', { rhythm: '舒缓铺垫' })]);
    const explosive = buildRhythmCurveModel([volume('卷一', { rhythm: '爆点-高潮-递进' })]);
    const profile = [
      RHYTHM_EXPECTED_INTENSITY.opening,
      RHYTHM_EXPECTED_INTENSITY.development,
      RHYTHM_EXPECTED_INTENSITY.midpoint,
      RHYTHM_EXPECTED_INTENSITY.climax,
      RHYTHM_EXPECTED_INTENSITY.resolution,
    ];
    expect(calm.points.map((point) => point.intensity)).toEqual(profile);
    expect(explosive.points.map((point) => point.intensity)).toEqual(profile);
    expect(profile).toEqual([2, 3, 4, 5, 2.5]);
  });

  it('passes rhythm and beat texts through for the tooltip and reports the empty state', () => {
    const model = buildRhythmCurveModel([
      volume('卷一', { midpoint: undefined, mid_twist: '假死反转', rhythm: ' 递进到爆点 ' }),
    ]);
    expect(model.points.every((point) => point.rhythmText === '递进到爆点')).toBe(true);
    expect(model.points.find((point) => point.beatKey === 'midpoint')?.beatText).toBe('假死反转');
    expect(buildRhythmCurveModel([]).empty).toBe(true);
    expect(buildRhythmCurveModel([]).points).toEqual([]);
  });
});
