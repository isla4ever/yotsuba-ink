import { ArrowRight, BookOpen, DatabaseZap, FileText, Library } from 'lucide-react';
import { useEffect, useState } from 'react';
import type { KnowledgeDocument, ProjectRecord } from '../../contracts';
import { listKnowledgeDocuments } from '../../services/knowledge';
import { listProjects } from '../../services/projectApi';
import { ManuscriptLoadingIndicator } from '../ManuscriptLoadingIndicator';

type Props = {
  /** Opens the project's Creation Shell, then jumps to its knowledge page. */
  onManageProject: (project: ProjectRecord) => void;
};

type ProjectDocs = {
  project: ProjectRecord;
  documents: KnowledgeDocument[];
};

/**
 * Studio-scoped knowledge overview: a cross-project read model. Documents are
 * stored per book (the retrieval corpus is project-private), so the global
 * page aggregates every book's shelf and links into the book for management.
 */
export function StudioKnowledgeOverview({ onManageProject }: Props) {
  const [groups, setGroups] = useState<ProjectDocs[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    const controller = new AbortController();
    (async () => {
      try {
        const projects = await listProjects(controller.signal);
        const loaded = await Promise.all(projects.map(async (project) => ({
          documents: await listKnowledgeDocuments(project.id).catch(() => [] as KnowledgeDocument[]),
          project,
        })));
        if (!controller.signal.aborted) setGroups(loaded);
      } catch (cause) {
        if (!controller.signal.aborted) setError(cause instanceof Error ? cause.message : '知识资料总览加载失败。');
      } finally {
        if (!controller.signal.aborted) setLoading(false);
      }
    })();
    return () => controller.abort();
  }, []);

  const docTotal = groups.reduce((sum, group) => sum + group.documents.length, 0);
  const chunkTotal = groups.reduce(
    (sum, group) => sum + group.documents.reduce((inner, doc) => inner + doc.chunk_count, 0),
    0,
  );

  return (
    <section aria-labelledby="studio-knowledge-title" className="studio-knowledge-overview workspace-page">
      <header className="workspace-page-head">
        <div className="workspace-page-title">
          <p className="eyebrow">工作室 · 全局视角</p>
          <h1 id="studio-knowledge-title"><BookOpen size={20} />知识资料总览</h1>
          <span>资料按作品私有存储并只注入自己的创作检索。这里纵览每本书的资料架，上传与删除请进入对应作品。</span>
        </div>
        <dl className="workspace-page-stats">
          <div><dt><Library size={13} />作品</dt><dd>{groups.length}</dd></div>
          <div><dt><FileText size={13} />资料</dt><dd>{docTotal}</dd></div>
          <div><dt><DatabaseZap size={13} />检索片段</dt><dd>{chunkTotal}</dd></div>
        </dl>
      </header>

      {error ? <p className="studio-inline-error" role="alert">{error}</p> : null}
      {loading ? (
        <div className="studio-loading-state" role="status">
          <ManuscriptLoadingIndicator />
          <strong>正在汇总各作品的知识资料</strong>
        </div>
      ) : groups.length === 0 && !error ? (
        <div className="studio-empty-state">
          <h2>还没有作品</h2>
          <p>新建作品后，它的知识资料会在这里汇总展示。</p>
        </div>
      ) : (
        <div className="studio-knowledge-groups">
          {groups.map(({ documents, project }) => (
            <article className="studio-knowledge-group" key={project.id}>
              <header>
                <div>
                  <h2>{project.title}</h2>
                  <span>{documents.length ? `${documents.length} 份资料 · ${documents.reduce((sum, doc) => sum + doc.chunk_count, 0)} 个片段` : '尚未上传资料'}</span>
                </div>
                <button className="ghost" onClick={() => onManageProject(project)} type="button">
                  进入作品管理
                  <ArrowRight size={13} />
                </button>
              </header>
              {documents.length ? (
                <ul className="studio-knowledge-doc-list">
                  {documents.map((doc) => (
                    <li key={doc.doc_id}>
                      <FileText aria-hidden="true" size={14} />
                      <strong>{doc.title}</strong>
                      <span>{doc.chunk_count} 片段</span>
                    </li>
                  ))}
                </ul>
              ) : null}
            </article>
          ))}
        </div>
      )}
    </section>
  );
}
