import { Activity, BookOpenText, Coins, GitCompareArrows, ShieldCheck } from 'lucide-react';
import { CharacterForceGraphPanel } from './CharacterForceGraphPanel';
import { QualityMonitorPanel } from './QualityMonitorPanel';
import { WikiMemoryPanel } from './WikiMemoryPanel';
import { WorldbuildingPanel } from './WorldbuildingPanel';
import type { ChapterProgressItem, RunEvent, WorkflowDefinition } from '../types/workflow';

type Props = {
  events: RunEvent[];
  memoryEvents: RunEvent[];
  workflow: WorkflowDefinition;
};

export function WritingWorkbench({ events, memoryEvents, workflow }: Props) {
  const chapters = chaptersFrom(events);
  const current = currentChapter(events);
  const content = writingContent(events);
  const variants = events.filter((event) => event.type === 'variant_generated' && event.chapter).slice(0, 8);
  const selected = events.filter((event) => event.type === 'best_variant_selected' && event.chapter).slice(0, 6);
  const tokenEvent = events.find((event) => event.type === 'token_estimate_updated' && event.token_estimates);
  const totalTokens = Number((tokenEvent?.token_estimates?.total_estimated_tokens as number | undefined) ?? 0);

  return (
    <section className="writing-workbench">
      <section className="writing-main">
        <div className="writing-head">
          <div>
            <p className="eyebrow">Writing Mode</p>
            <h2><BookOpenText size={18} />正文创作态</h2>
          </div>
          <div className="writing-metrics">
            <span>{current || '等待章节'} </span>
            <span>{content.length.toLocaleString()} 字符</span>
            <span>{workflow.quality_mode === 'deep' ? '深度精修' : workflow.quality_mode === 'fast' ? '极速预览' : '平衡创作'}</span>
          </div>
        </div>

        <div className="chapter-strip">
          {chapters.map((chapter) => (
            <article className={chapter.status} key={chapter.chapter}>
              <strong>{chapter.chapter}</strong>
              <span>{chapter.words} 字 · Q {chapter.quality_score ? chapter.quality_score.toFixed(2) : '-'}</span>
            </article>
          ))}
        </div>

        <article className="writing-editor">
          <div className="writing-editor-toolbar">
            <span><Activity size={14} />实时写入</span>
            <span>{current ? `${current} 正在汇入正文` : '等待正文事件'}</span>
          </div>
          <pre>{content || '正文创作阶段启动后，章节内容会在这里实时写入。'}</pre>
        </article>

        <div className="writing-bottom-grid">
          <section className="writing-card">
            <h3><GitCompareArrows size={15} />候选版本</h3>
            <div className="writing-list">
              {variants.map((event, index) => (
                <article key={`${event.chapter}-${index}`}>
                  <strong>{String(event.chapter ?? '')} · {String((event.variant as Record<string, unknown> | undefined)?.variant_id ?? 'candidate')}</strong>
                  <span>{String((event as RunEvent & { preview?: unknown }).preview ?? '').slice(0, 90)}</span>
                </article>
              ))}
              {!variants.length ? <p className="muted">当前模式未产生候选版本，或正文尚未开始。</p> : null}
            </div>
          </section>
          <section className="writing-card">
            <h3><ShieldCheck size={15} />最优选择</h3>
            <div className="writing-list">
              {selected.map((event, index) => (
                <article key={`${event.chapter}-selected-${index}`}>
                  <strong>{event.chapter} · Q {event.selected?.score?.toFixed(2) ?? '-'}</strong>
                  <span>{event.selected?.reason ?? '已选择当前最优版本'}</span>
                </article>
              ))}
              {!selected.length ? <p className="muted">平衡/深度模式会在这里显示评审择优结果。</p> : null}
            </div>
          </section>
          <section className="writing-card">
            <h3><Coins size={15} />Token 估算</h3>
            <div className="token-estimate">
              <strong>{totalTokens ? totalTokens.toLocaleString() : '-'}</strong>
              <span>演示估算 token</span>
            </div>
          </section>
        </div>
      </section>

      <aside className="writing-side">
        <CharacterForceGraphPanel events={events} />
        <WorldbuildingPanel events={events} />
        <WikiMemoryPanel events={[...events, ...memoryEvents]} />
        <QualityMonitorPanel events={events} stages={workflow.nodes} />
      </aside>
    </section>
  );
}

function chaptersFrom(events: RunEvent[]): ChapterProgressItem[] {
  const latest = events.find((event) => event.type === 'chapter_progress_updated' && event.chapters);
  return latest?.chapters?.length ? latest.chapters : [];
}

function currentChapter(events: RunEvent[]) {
  return events.find((event) => event.type === 'chapter_started')?.chapter ?? events.find((event) => event.type === 'chapter_delta')?.chapter ?? '';
}

function writingContent(events: RunEvent[]) {
  const chronological = [...events].reverse();
  const completed = chronological
    .filter((event) => event.type === 'chapter_completed' && event.content)
    .map((event) => `\n\n${event.chapter}\n${event.content}`);
  if (completed.length) return completed.join('\n').trim();
  return chronological
    .filter((event) => event.type === 'chapter_delta' && event.delta)
    .map((event) => event.delta)
    .join('\n');
}
