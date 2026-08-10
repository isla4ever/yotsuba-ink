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
    description: '沿同一 LangGraph 流程自动接受阶段与章节决策，适合快速得到完整草稿。',
    capability: '全流程自动推进；仍执行固定并行审稿；问题与决策回执完整保留。',
    cost: '不含人工换稿',
    useCase: '快速成稿',
    intervention: '无需人工干预',
    layout: '单页创作驾驶舱',
    icon: Zap,
  },
  balanced: {
    title: '平衡',
    shortLabel: '稳',
    description: '默认工作方式。每个阶段与每章都等待人工接受、定向换稿或取消。',
    capability: '连续性与人物审稿必需；文风审稿可选；候选仅按明确方向重新生成。',
    cost: '按换稿次数增加',
    useCase: '常规创作',
    intervention: '逐阶段与逐章确认',
    layout: '八阶段工作台 + 运行驾驶舱',
    icon: Gauge,
  },
  deep: {
    title: '精细',
    shortLabel: '精',
    description: '每个阶段与每章都停在人工决策点，确认或定向换稿后再继续。',
    capability: '逐阶段与逐章人工定稿；固定三路并行审稿全部必须返回；不自动改写正文。',
    cost: '按换稿次数增加',
    useCase: '正式稿精修',
    intervention: '逐阶段与逐章确认',
    layout: '逐阶段定稿工作台',
    icon: Layers3,
  },
} satisfies Record<QualityMode, QualityModeProfile>;

export const qualityModeColors = {
  fast: { accent: '#78aef8', accentStrong: '#8fc7ff' },
  balanced: { accent: '#2fd68f', accentStrong: '#43e7ba' },
  deep: { accent: '#8b5cf6', accentStrong: '#a778ff' },
} satisfies Record<QualityMode, { accent: string; accentStrong: string }>;
