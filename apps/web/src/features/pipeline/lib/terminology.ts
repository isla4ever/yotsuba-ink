import type { QualityMode } from '../contracts';
import { qualityModeProfiles } from './qualityModes';

/**
 * Phase 12 S4 (Wave 2C): 创作者语言词汇表。
 * 高频动词/名词的唯一用词来源——同一动作、同一概念在所有表面只允许一个叫法
 * （审计 C5-C25）。内部工程词（delta、上下文包、落盘、Provider、Canon、Token、
 * 阀门/闸门等）不出现在创作者可见文案里。
 */
export const TERM = {
  /** Provider 的创作者叫法（C7/C23）；设置页高级区可保留 Provider 原词。 */
  aiService: 'AI 服务',
  /** Beat Board 的中文名（C18）。 */
  beatBoard: '节拍板',
  /** Canon 的创作者叫法（C13）；Canon 只留在代码与类型名。 */
  canon: '正典',
  canonFacts: '正典事实',
  /** chapter_context / context packet 的创作者叫法（C5）。 */
  chapterContext: '章节上下文',
  /** 定稿动作的唯一动词（C9）：不再有「确认推荐/批准」。 */
  confirmFinal: '确认定稿',
  /** 流式 delta 的创作者叫法（C5）。 */
  contentUpdate: '内容更新',
  /** 模式体系的概念名（C12/M2）：不再有「质量模式/质量方式/生产模式」。 */
  creationMode: '创作模式',
  imageService: '图片服务',
  /** 质量体系的人工侧（C16）：不再有「人工闸门/定稿闸门」。 */
  manualCheckpoint: '人工定稿点',
  /** 提案采纳态（C10）：不再有「已授权/已接受」。 */
  proposalAccepted: '已采纳',
  /** 质量体系的机器侧（C16）：不再有「质量阀门/巡检」。 */
  qualityCheck: '质量检查',
  /** 换稿动作的唯一说法（C22）：不再有「换稿/换一版/重生成」。 */
  redraft: '换一稿',
  /** 落盘/持久化 的创作者叫法（C8）。 */
  saved: '已保存',
  /** 合同校验/结构校验 的创作者叫法（C3 收尾）。 */
  structureCheck: '结构检查',
  /** Token 的创作者叫法（C6）；设置页/诊断明细可保留 token。 */
  usageQuota: '用量额度',
} as const;

/** 模式名唯一来源是 qualityModeProfiles——这里只 re-export 引用，不复制文案。 */
export { qualityModeProfiles };

/** 创作模式档位名（C11/M2）：唯一取名途径，禁止在组件里手写模式名分支。 */
export function creationModeTitle(mode: QualityMode): string {
  return qualityModeProfiles[mode].title;
}
