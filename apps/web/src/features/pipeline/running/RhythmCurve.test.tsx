import { renderToStaticMarkup } from 'react-dom/server';
import { describe, expect, it } from 'vitest';
import type { OutlineVolume } from './outlinePresentation';
import { RhythmCurve } from './RhythmCurve';

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

describe('RhythmCurve', () => {
  it('exposes focusable beat points in reading order across volumes with boundary and active-volume highlight', () => {
    const html = renderToStaticMarkup(
      <RhythmCurve activeVolumeIndex={1} onSelectBeat={() => undefined} volumes={[volume('卷一'), volume('卷二')]} />,
    );
    const labels = Array.from(html.matchAll(/aria-label="([^"]*结构预期强度 [\d.]+\/5[^"]*)"/g)).map((match) => match[1]);
    expect(labels).toHaveLength(10);
    expect(labels[0]).toContain('卷一 开端');
    expect(labels[4]).toContain('卷一 结局');
    expect(labels[5]).toContain('卷二 开端');
    expect(labels[9]).toContain('卷二 结局');
    expect(html.match(/rhythm-curve-boundary/g)).toHaveLength(1);
    expect(html).toContain('rhythm-curve-active-band');
    expect(html.match(/in-active-volume/g)).toHaveLength(5);
  });

  it('renders a single volume without boundaries and labels the axis as structural expectation, not a score', () => {
    const html = renderToStaticMarkup(
      <RhythmCurve activeVolumeIndex={0} onSelectBeat={() => undefined} volumes={[volume('全一卷')]} />,
    );
    expect(html).not.toContain('rhythm-curve-boundary');
    expect(html.match(/rhythm-curve-point/g)).toHaveLength(5);
    expect(html).toContain('结构预期强度」轮廓（1–5，结构语义，非内容质量评分）');
    expect(html).toContain('（结构预期，非内容评分）');
  });
});
