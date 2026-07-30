import type { OutlineArtifact } from './stageArtifacts';
import { valueText } from './stageViewData';

export type OutlineVolume = OutlineArtifact['volumes'][number];
export type OutlineFocusKey = 'overview' | 'opening' | 'development' | 'midpoint' | 'climax' | 'resolution';

export const OUTLINE_BEAT_DEFINITIONS = [
  { key: 'opening', label: '开端', hint: '建立入口问题', tone: 'beat' },
  { key: 'development', label: '发展', hint: '证据互相咬合', tone: 'beat' },
  { key: 'midpoint', label: '中点', hint: '卷内反转', tone: 'turn' },
  { key: 'climax', label: '高潮', hint: '爆点推进', tone: 'turn' },
  { key: 'resolution', label: '结局', hint: '卷尾钩子', tone: 'turn' },
] as const;

export function outlineBeatItems(volume: OutlineVolume) {
  const values: Record<(typeof OUTLINE_BEAT_DEFINITIONS)[number]['key'], string> = {
    climax: volume.climax ?? '',
    development: volume.development ?? '',
    midpoint: volume.midpoint ?? volume.mid_twist ?? '',
    opening: volume.opening ?? '',
    resolution: volume.resolution ?? volume.volume_cliffhanger ?? '',
  };
  return OUTLINE_BEAT_DEFINITIONS.map((definition) => ({ ...definition, value: values[definition.key] }));
}

export function outlineDependencyItems(volume: OutlineVolume) {
  return [
    {
      count: volume.character_progression.length,
      dialog: 'character' as const,
      key: 'character_progression',
      label: '角色承接',
      target: '人物图谱',
      value: valueText(volume.character_progression) || '选择已定稿人物关系，补充本卷变化。',
    },
    {
      count: volume.world_reveal.length,
      dialog: 'worldbuilding' as const,
      key: 'world_reveal',
      label: '世界观承接',
      target: '世界观',
      value: valueText(volume.world_reveal) || '选择已定稿世界观锚点，补充本卷揭示。',
    },
    {
      count: volume.foreshadow_plan.length,
      dialog: 'foreshadow' as const,
      key: 'foreshadow_plan',
      label: '伏笔账本',
      target: '细纲与 Wiki 候选',
      value: valueText(volume.foreshadow_plan) || '记录本卷需要投放、推进或回收的线索。',
    },
  ];
}

export function volumeGoal(volume: OutlineVolume) {
  return volume.volume_goal || volume.goal || '等待补充分卷目标。';
}
