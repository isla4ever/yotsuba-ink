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
  /** 一句话回答"这个模式适合什么样的人"。 */
  audience: string;
  /** 一句话回答"什么场景该用它"。 */
  scenario: string;
  icon: LucideIcon;
};

export const qualityModeProfiles = {
  fast: {
    title: '极速',
    shortLabel: '快',
    description: '沿同一 LangGraph 流程自动接受阶段与章节决策，适合快速得到完整草稿。',
    capability: '全流程自动推进；分卷、转折、人物数量由系统按篇幅直接取值；仍执行固定并行审稿。',
    cost: '不含人工换稿',
    useCase: '快速成稿',
    intervention: '无需人工干预',
    layout: '创作控制台（卷章结构 + 内容 + 日志同屏）',
    audience: '想先看到完整成书、不想逐项把关的作者',
    scenario: '灵感验证、短篇试写、批量产出初稿',
    icon: Zap,
  },
  balanced: {
    title: '平衡',
    shortLabel: '稳',
    description: '默认工作方式。每个阶段与每章都等待人工接受、定向换稿或取消。',
    capability: '结构取值在系统建议区间内由剧情自选；连续性与人物审稿必需；文风审稿可选。',
    cost: '按换稿次数增加',
    useCase: '常规创作',
    intervention: '逐阶段与逐章确认',
    layout: '阶段工作台 + 可切换创作控制台',
    audience: '想握住关键节点、其余交给系统的日常创作者',
    scenario: '中长篇连载的常规创作与续写',
    icon: Gauge,
  },
  deep: {
    title: '精细',
    shortLabel: '精',
    description: '每个阶段与每章都停在人工决策点，确认或定向换稿后再继续，并可自定义卷数、转折数与人物数量。',
    capability: '逐阶段与逐章人工定稿；篇幅包络支持锁定结构取值；固定三路并行审稿全部必须返回。',
    cost: '按换稿次数增加',
    useCase: '正式稿精修',
    intervention: '逐阶段与逐章确认',
    layout: '逐阶段精修工作台',
    audience: '追求出版级质量、要求结构强控制的资深作者',
    scenario: '正式稿精修，自定义卷数、转折与人物数量',
    icon: Layers3,
  },
} satisfies Record<QualityMode, QualityModeProfile>;

export const qualityModeColors = {
  fast: { accent: '#78aef8', accentStrong: '#8fc7ff' },
  balanced: { accent: '#2fd68f', accentStrong: '#43e7ba' },
  deep: { accent: '#8b5cf6', accentStrong: '#a778ff' },
} satisfies Record<QualityMode, { accent: string; accentStrong: string }>;
