import { DatabaseZap, FileText, UploadCloud } from 'lucide-react';
import type { KnowledgeDocument, RunEvent } from '../../contracts';

type Props = {
  documents: KnowledgeDocument[];
  events: RunEvent[];
  onOpenKnowledge: () => void;
};

export function RuntimeKnowledgePanel({ documents, events, onOpenKnowledge }: Props) {
  const ragEvents = events.filter((event) => event.type.startsWith('rag_') || event.type.startsWith('reference_'));
  const chunks = documents.reduce((sum, doc) => sum + (doc.chunk_count || 0), 0);
  return (
    <section className="config-section runtime-insight-card runtime-knowledge-card">
      <div className="runtime-knowledge-head">
        <h3><DatabaseZap size={16} />知识库资料台</h3>
        <button aria-label="上传或管理知识库资料" className="insight-edit-button" onClick={onOpenKnowledge} title="上传或管理资料" type="button">
          <UploadCloud size={14} />
        </button>
      </div>
      <div className="runtime-insight-grid">
        <strong>{documents.length}<span>资料</span></strong>
        <strong>{chunks}<span>片段</span></strong>
        <strong>{ragEvents.length}<span>事件</span></strong>
      </div>
      <div className="runtime-knowledge-list">
        {documents.slice(0, 4).map((doc) => (
          <article key={doc.doc_id}>
            <FileText size={13} />
            <div>
              <strong>{doc.title || doc.filename}</strong>
              <span>{doc.status} · {doc.chunk_count} 片段</span>
            </div>
          </article>
        ))}
        {!documents.length ? (
          <p className="muted">暂无项目资料。创作立项只使用故事输入与已确认的前置参考；上传并选中资料后才会检索项目知识库。</p>
        ) : null}
      </div>
    </section>
  );
}
