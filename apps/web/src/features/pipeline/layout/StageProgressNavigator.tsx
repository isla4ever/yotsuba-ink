import { useState, type CSSProperties } from 'react';
import { motion } from 'motion/react';
import { createPortal } from 'react-dom';
import { SlidersHorizontal } from 'lucide-react';
import type { ConfigProgress, RunEvent, WorkflowStage } from '../contracts';

type Props = {
  stage: WorkflowStage;
  events: RunEvent[];
  configProgress?: ConfigProgress;
};

const ECG_PATH = 'M0 12 H18 L21 12 L22.4 5 L24.2 19 L26 12 H42 L45 12 L46.4 8 L48.2 15.5 L50 12 H63 L66 12 L67.6 4 L70 20 L72.3 12 H84 L87 12 L88.8 8.2 L91 15.8 L93.3 12 H100';

export function StageProgressNavigator({ stage, events, configProgress }: Props) {
  const progress = configProgress ?? fallbackProgress(stage, events);
  const items = progress.items;
  const activeIndex = Math.min(progress.completed, items.length - 1);
  const [hoverTooltip, setHoverTooltip] = useState<{ key: string; x: number; y: number } | null>(null);
  const activeItem = items.find((item) => item.key === hoverTooltip?.key) ?? null;

  const showTooltip = (itemKey: string, target: HTMLElement) => {
    const rect = target.getBoundingClientRect();
    setHoverTooltip({ key: itemKey, x: rect.left + rect.width / 2, y: rect.bottom + 10 });
  };

  return (
    <section className="stage-mini-progress config-ready" aria-label="配置准备进度">
      <div className="stage-mini-title">
        <SlidersHorizontal size={15} />
        <div>
          <span>配置准备</span>
          <strong>配置进度 {progress.completed}/{items.length}</strong>
        </div>
      </div>
      <div className="stage-mini-track" style={{ '--steps': items.length } as CSSProperties}>
        <div className="stage-mini-line">
          <svg aria-hidden="true" className="stage-mini-ecg-wave" preserveAspectRatio="none" viewBox="0 0 100 24">
            <defs>
              <filter id="ecg-glow" x="-80%" y="-80%" width="260%" height="260%">
                <feGaussianBlur stdDeviation="1.8" result="blur" />
                <feMerge>
                  <feMergeNode in="blur" />
                  <feMergeNode in="SourceGraphic" />
                </feMerge>
              </filter>
            </defs>
            <path className="ecg-base" d={ECG_PATH} pathLength={100} />
            <path className="ecg-signal-tail-path" d={ECG_PATH} pathLength={100} />
          </svg>
        </div>
        <div className="stage-mini-dots">
          {items.map((item, index) => {
            const active = index === activeIndex;
            return (
              <motion.button
                animate={{ opacity: 1, scale: 1 }}
                aria-label={`${item.label}：${item.done ? '已完成' : '待配置'}`}
                className={item.done ? 'done' : active ? 'current' : ''}
                initial={{ opacity: 0, scale: 0.88 }}
                key={item.key}
                onBlur={() => setHoverTooltip((current) => (current?.key === item.key ? null : current))}
                onFocus={(event) => showTooltip(item.key, event.currentTarget)}
                onMouseEnter={(event) => showTooltip(item.key, event.currentTarget)}
                onMouseLeave={() => setHoverTooltip((current) => (current?.key === item.key ? null : current))}
                transition={{ delay: index * 0.025 }}
                type="button"
              />
            );
          })}
        </div>
        {activeItem && hoverTooltip ? createPortal(
          <div
            className={`config-progress-popover ${activeItem.done ? 'done' : 'pending'}`}
            style={{ '--popover-x': `${hoverTooltip.x}px`, '--popover-y': `${hoverTooltip.y}px` } as CSSProperties}
          >
            <strong>{activeItem.label}</strong>
            <span>{activeItem.done ? '已完成' : '待配置'}</span>
            <p>{configTooltipCopy[activeItem.key]?.description ?? '检查当前配置项是否满足运行前置条件。'}</p>
            {!activeItem.done ? <em>{configTooltipCopy[activeItem.key]?.next ?? '请补全该项配置。'}</em> : null}
          </div>,
          document.body,
        ) : null}
      </div>
    </section>
  );
}

const configTooltipCopy: Record<string, { description: string; next: string }> = {
  model: {
    description: '用于检查可用文本 / 图像模型通道，确认创作节点有可调用的 Provider。',
    next: '请在设置中配置可用 API，或启用本地演示通道。',
  },
  brief: {
    description: '检查题材、篇幅、受众、核心冲突、关键词和禁忌是否完整。',
    next: '请补齐小说推荐阶段的核心 Brief 输入。',
  },
  reference: {
    description: '检查智能搜索、指定链接或知识库检索是否具备参考输入。',
    next: '请选择参考源，并提供关键词、链接或检索意图。',
  },
  knowledge: {
    description: '仅 RAG / 关闭联网时强制需要资料，其余场景作为用户私有补充约束。',
    next: '请上传项目资料，或切换为智能联网搜索。',
  },
  quality: {
    description: '检查质量模式、最低评分和版本择优策略是否有效。',
    next: '请确认质量阀门配置在有效范围内。',
  },
};

function fallbackProgress(stage: WorkflowStage, events: RunEvent[]): ConfigProgress {
  const labels = progressItemsFor(stage);
  const completed = completedCount(stage, events, labels.length);
  const items = labels.map((label, index) => ({ key: `${stage.id}-${index}`, label, done: index < completed }));
  return { completed: items.filter((item) => item.done).length, items };
}

function progressItemsFor(stage: WorkflowStage) {
  if (stage.type === 'info_recommend') return ['需求录入', '题材分析', '候选方案', '人设种子'];
  if (stage.type === 'summary') return ['主线', '角色弧', '反转', '结局'];
  if (stage.type === 'outline') {
    const count = numberField(stage, 'volume_count', 3);
    return compactRange(count, '第', '卷');
  }
  if (stage.type === 'detail_outline') {
    const count = numberField(stage, 'chapter_count', 6);
    return compactRange(count, '', '章');
  }
  if (stage.type === 'chapter_text') {
    const count = Math.max(3, Math.min(8, numberField(stage, 'version_candidate_count', 3)));
    return compactRange(count, '第', '章');
  }
  if (stage.type === 'cover_image') return ['提示词', '构图', '生成', '预览'];
  return ['汇总', '校验', '打包', '完成'];
}

function completedCount(stage: WorkflowStage, events: RunEvent[], total: number) {
  const status = events.find((event) => event.node_id === stage.id && event.type.startsWith('node_'))?.type;
  if (status === 'node_completed') return total;
  if (status === 'node_started') return Math.max(1, Math.floor(total / 3));
  if (stage.type === 'outline') return 1;
  if (stage.type === 'detail_outline') return 2;
  if (stage.type === 'chapter_text') return 1;
  return 0;
}

function subtitleFor(stage: WorkflowStage, completed: number, total: number, versionCompare: boolean) {
  if (stage.type === 'outline') return `分卷进度 ${completed}/${total}`;
  if (stage.type === 'detail_outline') return `章节细纲 ${completed}/${total}`;
  if (stage.type === 'chapter_text') return `正文生成 ${completed}/${total}${versionCompare ? ' · 版本比对开启' : ' · 单版本模式'}`;
  if (stage.type === 'cover_image') return `封面产物 ${completed}/${total}`;
  if (stage.type === 'export_artifact') return `导出流程 ${completed}/${total}`;
  return `阶段进度 ${completed}/${total}`;
}

function numberField(stage: WorkflowStage, key: string, fallback: number) {
  const value = stage.input_schema.find((field) => field.key === key)?.default;
  return typeof value === 'number' && Number.isFinite(value) ? value : fallback;
}

function compactRange(count: number, prefix: string, suffix: string) {
  if (count <= 6) return Array.from({ length: count }, (_, index) => `${prefix}${index + 1}${suffix}`);
  return ['1-2', '3-4', '5-6', `${count - 1}-${count}`].map((range) => `${prefix}${range}${suffix}`);
}
