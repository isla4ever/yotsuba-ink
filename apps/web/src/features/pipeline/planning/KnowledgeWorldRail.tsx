import { CheckCircle2, DatabaseZap, FileText, FolderOpen, Globe2, Search, Settings2 } from 'lucide-react';
import type { KnowledgeDocument, RunEvent } from '../contracts';
import { knowledgeBackendLabel } from '../services/knowledge';

type Props = {
  documents: KnowledgeDocument[];
  events: RunEvent[];
  onOpenKnowledge: () => void;
};

export function KnowledgeWorldRail({ documents, events, onOpenKnowledge }: Props) {
  const chunkCount = documents.reduce((sum, item) => sum + item.chunk_count, 0);
  const latestRag = events.find((event) => event.type === 'rag_results_found' || event.type === 'web_results_found' || event.type === 'reference_context_merged');
  const health = documents.length ? '资料已接入' : latestRag ? '联网参考就绪' : '等待资料';
  const backend = knowledgeBackendLabel(documents);

  return (
    <aside className="knowledge-world-rail">
      <section className="knowledge-mini-card">
        <div className="knowledge-mini-head">
          <div className="knowledge-mini-copy">
            <p className="eyebrow">创作依据</p>
            <h3><DatabaseZap size={15} />知识库</h3>
            <span className={`knowledge-health ${documents.length || latestRag ? 'ready' : ''}`}><CheckCircle2 size={12} />{health}</span>
          </div>
          <button className="ghost knowledge-manage-action" onClick={onOpenKnowledge} type="button"><Settings2 size={14} />管理资料</button>
        </div>
        <div className="planning-knowledge-summary">
          <div className="planning-knowledge-metrics" aria-label="知识库准备状态">
            <span><FileText size={13} /><strong>{documents.length}</strong><em>文档</em></span>
            <span><Search size={13} /><strong>{chunkCount}</strong><em>片段</em></span>
            <span><DatabaseZap size={13} /><strong>{backend}</strong><em>索引</em></span>
          </div>
          {documents.length ? (
            <div className="planning-knowledge-source">
              <FileText size={13} />
              <strong>{documents[0].title}</strong>
              <span>{documents.length > 1 ? `另有 ${documents.length - 1} 份资料` : `${chunkCount} 个检索片段`}</span>
            </div>
          ) : (
            <div className="planning-knowledge-source empty">
              <FolderOpen size={14} />
              <strong>未添加项目资料</strong>
              <span>知识库可选</span>
            </div>
          )}
          <div className="planning-reference-status">
            <Globe2 size={13} />
            <span>{latestRag ? statusText(latestRag.type) : '联网参考将在立项阶段按配置使用'}</span>
          </div>
        </div>
      </section>
    </aside>
  );
}

function statusText(type: string) {
  if (type === 'web_results_found') return '已获取联网参考，将优先作为创作依据。';
  if (type === 'rag_results_found') return '已完成用户知识库检索。';
  return '参考上下文已合并。';
}
