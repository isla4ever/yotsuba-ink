import { DatabaseZap, FileText, Settings2 } from 'lucide-react';
import { WorldbuildingPanel } from './WorldbuildingPanel';
import type { KnowledgeDocument, RunEvent } from '../types/workflow';
import { knowledgeBackendLabel } from '../utils/knowledgeBase';

type Props = {
  documents: KnowledgeDocument[];
  events: RunEvent[];
  onOpenKnowledge: () => void;
};

export function KnowledgeWorldRail({ documents, events, onOpenKnowledge }: Props) {
  const chunkCount = documents.reduce((sum, item) => sum + item.chunk_count, 0);
  const latestRag = events.find((event) => event.type === 'rag_results_found' || event.type === 'web_results_found' || event.type === 'reference_context_merged');

  return (
    <aside className="knowledge-world-rail">
      <section className="knowledge-mini-card">
        <div className="knowledge-mini-head">
          <div>
            <p className="eyebrow">Knowledge Base</p>
            <h3><DatabaseZap size={15} />知识库</h3>
          </div>
          <button className="icon-button tech-icon-button" onClick={onOpenKnowledge} title="管理知识库"><Settings2 size={14} /></button>
        </div>
        <div className="knowledge-mini-stats">
          <strong>{documents.length}<span>文档</span></strong>
          <strong>{chunkCount}<span>片段</span></strong>
        </div>
        <span className={knowledgeBackendLabel(documents).includes('待') ? 'kb-backend warn' : 'kb-backend'}>{knowledgeBackendLabel(documents)}</span>
        <div className="knowledge-mini-list">
          {documents.slice(0, 3).map((doc) => (
            <article key={doc.doc_id}>
              <FileText size={12} />
              <span>{doc.title}</span>
              <em>{doc.chunk_count}</em>
            </article>
          ))}
          {!documents.length ? <p>暂无资料。RAG 模式运行前会引导上传。</p> : null}
        </div>
        <small>{latestRag ? statusText(latestRag.type) : '联网开启时也会同步检索此知识库。'}</small>
      </section>
      <WorldbuildingPanel events={events} />
    </aside>
  );
}

function statusText(type: string) {
  if (type === 'web_results_found') return '已获取联网参考，优先注入 Prompt。';
  if (type === 'rag_results_found') return '已完成用户知识库检索。';
  return '参考上下文已合并。';
}
