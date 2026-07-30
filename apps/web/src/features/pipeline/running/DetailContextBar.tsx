import { BookOpenCheck, GitBranch, ListChecks } from 'lucide-react';
import type { DetailReadiness } from './detailArtifactModel';
import { detailMemoryCounts, type DetailChapter } from './detailPresentation';
import type { DetailOutlineArtifact } from './stageArtifacts';

type Props = {
  artifact: DetailOutlineArtifact;
  generating: boolean;
  legacyFinalized?: boolean;
  readiness: DetailReadiness;
  selectedChapter: DetailChapter | null;
};

export function DetailContextBar({ artifact, generating, legacyFinalized = false, readiness, selectedChapter }: Props) {
  const counts = detailMemoryCounts(artifact);
  const percentage = readiness.total ? Math.round((readiness.completed / readiness.total) * 100) : 0;
  return (
    <section aria-label="章节施工上下文" className="detail-context-bar">
      <div className="detail-context-title">
        <span><ListChecks size={13} />施工决策</span>
        <strong>{artifact.chapters.length} 章 · 当前：{selectedChapter?.chapter || '等待章节'}</strong>
        <small>{selectedChapter?.continuity_notes ? `正文交接：${selectedChapter.continuity_notes}` : '确认每章蓝图能否直接进入正文施工。'}</small>
      </div>
      <div aria-label="章节写回规模" className="detail-context-counts">
        <span><BookOpenCheck size={13} /><b>{counts.fact}</b> 事实 / Wiki</span>
        <span><GitBranch size={13} /><b>{counts.clue}</b> 伏笔动作</span>
      </div>
      <div aria-label={`内容完整度 ${readiness.completed}/${readiness.total}`} className={`detail-readiness ${readiness.ready ? 'ready' : ''}`} role="status">
        <div><span>{legacyFinalized ? '新版结构覆盖' : '内容完整度'}</span><strong>{readiness.completed}/{readiness.total}</strong></div>
        <i><b style={{ width: `${percentage}%` }} /></i>
        <small>{generating ? '章节施工图生成中' : legacyFinalized ? '按历史合同完成；新一轮创作将补齐结构化写回字段' : readiness.ready ? '可进入正文施工' : `待补：${readiness.missingLabels[0] || '章节字段'}`}</small>
      </div>
    </section>
  );
}
