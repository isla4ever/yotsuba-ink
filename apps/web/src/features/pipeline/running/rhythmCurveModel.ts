import { OUTLINE_BEAT_DEFINITIONS, outlineBeatItems, type OutlineVolume } from './outlinePresentation';

/**
 * Phase 10.3a 全书节奏折线模型（纯函数）：
 *
 * - 横轴：每卷五段节拍（opening/development/midpoint/climax/resolution）按卷
 *   顺序连续排布；第 v 卷第 b 拍的 order = v*5+b，xFraction=(order+0.5)/(5*卷数)。
 * - 纵轴：「结构预期强度」——叙事学标准五段结构的固定轮廓
 *   （开端 2 / 发展 3 / 中点 4 / 高潮 5 / 结局 2.5）。它是结构语义（每卷五段
 *   在全书中的预期起伏），不是对内容质量的模型评分；曲线值与卷内容无关。
 * - 卷的 rhythm 原文与节拍正文只进 tooltip/读出行展示，绝不改变曲线值。
 */
export const RHYTHM_EXPECTED_INTENSITY = {
  climax: 5,
  development: 3,
  midpoint: 4,
  opening: 2,
  resolution: 2.5,
} as const;

export const RHYTHM_INTENSITY_MAX = 5;

export type OutlineBeatKey = (typeof OUTLINE_BEAT_DEFINITIONS)[number]['key'];

export type RhythmCurvePoint = {
  beatKey: OutlineBeatKey;
  beatLabel: string;
  beatText: string;
  intensity: number;
  order: number;
  rhythmText: string;
  volumeIndex: number;
  volumeTitle: string;
  xFraction: number;
};

export type RhythmCurveModel = {
  boundaries: Array<{ afterVolumeIndex: number; fraction: number }>;
  empty: boolean;
  points: RhythmCurvePoint[];
  volumeSpans: Array<{ endFraction: number; rhythmText: string; startFraction: number; title: string }>;
};

export function buildRhythmCurveModel(volumes: OutlineVolume[]): RhythmCurveModel {
  const volumeCount = volumes.length;
  const beatCount = OUTLINE_BEAT_DEFINITIONS.length;
  const totalBeats = volumeCount * beatCount;
  const points: RhythmCurvePoint[] = volumes.flatMap((volume, volumeIndex) => {
    const volumeTitle = volume.title.trim() || `第${volumeIndex + 1}卷`;
    const rhythmText = (volume.rhythm ?? '').trim();
    return outlineBeatItems(volume).map((beat, beatIndex) => {
      const order = volumeIndex * beatCount + beatIndex;
      return {
        beatKey: beat.key,
        beatLabel: beat.label,
        beatText: beat.value.trim(),
        intensity: RHYTHM_EXPECTED_INTENSITY[beat.key],
        order,
        rhythmText,
        volumeIndex,
        volumeTitle,
        xFraction: (order + 0.5) / totalBeats,
      };
    });
  });
  return {
    boundaries: volumes.slice(1).map((_, index) => ({ afterVolumeIndex: index, fraction: (index + 1) / volumeCount })),
    empty: volumeCount === 0,
    points,
    volumeSpans: volumes.map((volume, index) => ({
      endFraction: (index + 1) / volumeCount,
      rhythmText: (volume.rhythm ?? '').trim(),
      startFraction: index / volumeCount,
      title: volume.title.trim() || `第${index + 1}卷`,
    })),
  };
}
