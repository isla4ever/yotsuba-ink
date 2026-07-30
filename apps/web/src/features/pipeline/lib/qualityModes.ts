import { Gauge, Layers3, Zap, type LucideIcon } from 'lucide-react';
import type { QualityMode } from '../contracts';

export type QualityModeProfile = {
  title: string;
  shortLabel: string;
  description: string;
  capability: string;
  cost: string;
  useCase: string;
  intervention: string;
  layout: string;
  icon: LucideIcon;
};

export const qualityModeProfiles = {
  fast: {
    title: '极速',
    shortLabel: '快',
    description: '全程自动推进，不跳转阶段页面，适合快速得到完整成稿。',
    capability: '全流程自动推进；单版本；轻质量检查；不设人工定稿点。',
    cost: '低消耗',
    useCase: '快速成稿',
    intervention: '无需人工干预',
    layout: '单页创作驾驶舱',
    icon: Zap,
  },
  balanced: {
    title: '平衡',
    shortLabel: '稳',
    description: '默认工作方式。信息推荐阶段人工定稿，确认后后续阶段自动推进。',
    capability: '信息推荐人工确认；后续自动；关键阶段保留有限候选择优。',
    cost: '中等消耗',
    useCase: '常规创作',
    intervention: '仅信息推荐定稿',
    layout: '定稿后自动驾驶舱',
    icon: Gauge,
  },
  deep: {
    title: '精细',
    shortLabel: '精',
    description: '每个阶段生成后都停在人工定稿点，逐段修改、确认后再进入下一阶段。',
    capability: '逐阶段人工定稿；多候选对比；更严格质量复检。',
    cost: '高消耗',
    useCase: '正式稿精修',
    intervention: '每阶段人工确认',
    layout: '逐阶段定稿工作台',
    icon: Layers3,
  },
} satisfies Record<QualityMode, QualityModeProfile>;

export const qualityModeColors = {
  fast: { accent: '#78aef8', accentStrong: '#8fc7ff' },
  balanced: { accent: '#2fd68f', accentStrong: '#43e7ba' },
  deep: { accent: '#8b5cf6', accentStrong: '#a778ff' },
} satisfies Record<QualityMode, { accent: string; accentStrong: string }>;

export function controlModeForQuality(mode: QualityMode) {
  if (mode === 'fast') return 'auto';
  if (mode === 'deep') return 'step';
  return 'info_step';
}
