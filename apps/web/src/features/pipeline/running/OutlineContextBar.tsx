import { CircleCheck, Layers3 } from 'lucide-react';
import type { OutlineReadiness } from './outlineArtifactModel';
import type { OutlineVolume } from './outlinePresentation';

type Props = {
  activeVolume: OutlineVolume | null;
  generating: boolean;
  legacyFinalized?: boolean;
  readiness: OutlineReadiness;
  volumeCount: number;
};

export function OutlineContextBar({ activeVolume, generating, legacyFinalized = false, readiness, volumeCount }: Props) {
  const status = generating
    ? '正在定型当前分卷'
    : legacyFinalized
      ? '按历史合同完成；新一轮创作将补齐结构化承接字段'
    : readiness.ready
      ? '可进入章节施工'
      : readiness.missingLabels.length
        ? `待补：${readiness.missingLabels[0]}${readiness.missingLabels.length > 1 ? ` 等 ${readiness.missingLabels.length} 项` : ''}`
        : '等待分卷产物';

  return (
    <section aria-label="分卷规划上下文" className="outline-context-bar">
      <div className="outline-context-title">
        <span><Layers3 size={14} />结构决策</span>
        <strong>{volumeCount} 卷 · {activeVolume?.chapter_range || '章节待定'}</strong>
        <small>当前审阅：{activeVolume?.title || '等待分卷产物'}</small>
      </div>
      <div aria-label={`内容完整度 ${readiness.completed}/${readiness.total}`} className={`outline-readiness ${readiness.ready ? 'ready' : 'incomplete'}`} role="status">
        <div><span>{readiness.ready ? <CircleCheck size={14} /> : null}{legacyFinalized ? '新版结构覆盖' : '内容完整度'}</span><strong>{readiness.completed}/{readiness.total}</strong></div>
        <i aria-hidden="true"><b style={{ width: readiness.total ? `${Math.round((readiness.completed / readiness.total) * 100)}%` : '0%' }} /></i>
        <small>{status}</small>
      </div>
    </section>
  );
}
