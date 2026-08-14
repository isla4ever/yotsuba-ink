import { ArrowLeft, BookOpen, BookOpenText, CheckCircle2, CircleDashed, Clock3, Loader2, PenLine, Settings } from 'lucide-react';
import { useRunStateContext, useUICommandContext, useWorkflowConfigContext } from '../../state/pipelineShellContext';
import type { MonitorChapterStatus, MonitorSnapshot } from './monitorModel';
import { monitorChapterStatusLabel, monitorStageStatusLabel } from './monitorModel';

export type MonitorSelection =
  | { kind: 'stage'; stageId: string }
  | { kind: 'chapter'; chapterRef: string };

type Props = {
  snapshot: MonitorSnapshot;
  selection: MonitorSelection;
  onSelect: (selection: MonitorSelection) => void;
};

/**
 * The console's own left rail: it owns the shell sidebar slot on /monitor, so
 * the book skeleton (volume→chapter) is the primary navigation and the global
 * entries the shell sidebar normally carries move to the rail footer.
 */
export function MonitorSidebar({ snapshot, selection, onSelect }: Props) {
  const { knowledgeDocuments, project } = useWorkflowConfigContext();
  const run = useRunStateContext();
  const ui = useUICommandContext();
  const hasTree = snapshot.tree.length > 0;
  return (
    <nav aria-label="监控导航" className="monitor-sidebar">
      <header className="monitor-rail-head">
        <button
          aria-label="返回工作室"
          className="monitor-rail-back"
          onClick={ui.navigateStudio}
          title="返回作品工作室（运行会话保留）"
          type="button"
        >
          <ArrowLeft size={14} />
        </button>
        <span className="monitor-rail-title" title={project?.title || snapshot.brief?.title || ''}>
          {project?.title || snapshot.brief?.title || '未归档创作'}
        </span>
      </header>

      <div className="monitor-rail-scroll">
        <p className="monitor-sidebar-caption">创作流程</p>
        <ul className={`monitor-stage-list${hasTree ? ' condensed' : ''}`}>
          {snapshot.stages.map((stage) => {
            const active = selection.kind === 'stage' && selection.stageId === stage.id;
            return (
              <li key={stage.id}>
                <button
                  aria-current={active ? 'true' : undefined}
                  className={`monitor-stage-item status-${stage.status}${active ? ' active' : ''}`}
                  onClick={() => onSelect({ kind: 'stage', stageId: stage.id })}
                  type="button"
                >
                  <span className={`monitor-stage-dot status-${stage.status}`} />
                  <span className="monitor-stage-item-copy">
                    <strong>{stage.label}</strong>
                    {!hasTree ? <small>{stage.metric || monitorStageStatusLabel[stage.status]}</small> : null}
                  </span>
                </button>
              </li>
            );
          })}
        </ul>
        {hasTree ? (
          <>
            <p className="monitor-sidebar-caption">
              <BookOpenText size={14} />
              书籍结构 · {snapshot.totals.chaptersDone}/{snapshot.totals.chaptersTotal} 章定稿
            </p>
            <div className="monitor-tree">
              {snapshot.tree.map((volume) => (
                <section className="monitor-tree-volume" key={volume.ref}>
                  <header>
                    <span className="monitor-tree-volume-ordinal">卷 {volume.ordinal}</span>
                    <span className="monitor-tree-volume-promise" title={volume.promise}>{volume.promise || volume.ref}</span>
                  </header>
                  <ul>
                    {volume.chapters.map((chapter) => {
                      const active = selection.kind === 'chapter' && selection.chapterRef === chapter.ref;
                      return (
                        <li key={chapter.ref}>
                          <button
                            aria-current={active ? 'true' : undefined}
                            className={`monitor-tree-chapter status-${chapter.status}${active ? ' active' : ''}`}
                            onClick={() => onSelect({ chapterRef: chapter.ref, kind: 'chapter' })}
                            type="button"
                          >
                            <ChapterStatusIcon status={chapter.status} />
                            <span className="monitor-tree-chapter-copy">
                              <strong>{chapter.title || chapter.purpose || chapter.ref}</strong>
                              <small>
                                {monitorChapterStatusLabel[chapter.status]}
                                {chapter.words ? ` · ${chapter.words.toLocaleString()} 字` : ''}
                              </small>
                            </span>
                          </button>
                        </li>
                      );
                    })}
                  </ul>
                </section>
              ))}
            </div>
          </>
        ) : (
          <p className="monitor-sidebar-caption is-hint">
            <CircleDashed size={14} />
            细纲完成后，这里会展开卷→章结构树
          </p>
        )}
      </div>

      <div aria-label="全局入口" className="monitor-rail-foot" role="group">
        <button className="monitor-rail-link" onClick={ui.openKnowledge} title="管理项目资料与检索依据" type="button">
          <BookOpen size={15} />
          <span>知识资料</span>
          {knowledgeDocuments.length ? <em>{knowledgeDocuments.length}</em> : null}
        </button>
        <button className="monitor-rail-link" onClick={ui.openHistory} title="查看运行、快照与导出版本" type="button">
          <Clock3 size={15} />
          <span>创作历史</span>
          {run.historyItems.length ? <em>{run.historyItems.length}</em> : null}
        </button>
        <button className="monitor-rail-link" onClick={ui.openSettings} title="编辑服务、模型和工作流偏好" type="button">
          <Settings size={15} />
          <span>模型与设置</span>
        </button>
      </div>
    </nav>
  );
}

function ChapterStatusIcon({ status }: { status: MonitorChapterStatus }) {
  if (status === 'done') return <CheckCircle2 className="monitor-chapter-icon done" size={15} />;
  if (status === 'writing') return <Loader2 className="monitor-chapter-icon writing spin" size={15} />;
  if (status === 'reviewing') return <PenLine className="monitor-chapter-icon reviewing" size={15} />;
  return <CircleDashed className="monitor-chapter-icon pending" size={15} />;
}
