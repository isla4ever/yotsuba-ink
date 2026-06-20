import { Activity, BookOpenText, Boxes, CheckCircle2, FileText, GitCompareArrows, Layers3, ListChecks, RefreshCw, Search, ShieldCheck, Sparkles } from 'lucide-react';
import { useEffect, useState } from 'react';
import type { RunEvent, WorkflowDefinition, WorkflowStage } from '../contracts';
import { chapterQualityClass, chapterQualityLabel, chaptersFrom, currentChapter, labelForRag, referenceEventText, writingContent } from './stageRunUtils';

export function InfoStageView({
  approvalDraft,
  approvalPending,
  referenceEvents,
  stage,
  onApprovalDraftChange,
  onApproveBrief,
  onRegenerateBrief,
}: {
  approvalDraft: string;
  approvalPending: boolean;
  referenceEvents: RunEvent[];
  stage: WorkflowStage;
  onApprovalDraftChange: (value: string) => void;
  onApproveBrief: (artifact: string) => void;
  onRegenerateBrief: () => void;
}) {
  const defaults = Object.fromEntries(stage.input_schema.map((field) => [field.key, field.default]));
  const [collapsed, setCollapsed] = useState(false);
  useEffect(() => {
    if (referenceEvents.some((event) => event.type === 'reference_context_injected')) setCollapsed(true);
  }, [referenceEvents]);
  return (
    <div className="stage-run-grid">
      <section className="stage-run-card">
        <h3><Sparkles size={15} />立项输入</h3>
        <div className="brief-readout">
          <span>题材：{String(defaults.genre ?? '-')}</span>
          <span>篇幅：{String(defaults.target_length ?? '-')} · {String(defaults.target_words_range ?? '-')}</span>
          <span>读者：{String(defaults.audience ?? '-')}</span>
          <p>{String(defaults.core_concept ?? '')}</p>
        </div>
      </section>
      <section className="stage-run-card">
        <h3>
          <Search size={15} />参考抓取与理解
          {referenceEvents.length ? <button className="ghost tiny-action" onClick={() => setCollapsed((value) => !value)} type="button">{collapsed ? '展开' : '收起'}</button> : null}
        </h3>
        <div className={collapsed ? 'rag-event-list collapsed' : 'rag-event-list'}>
          {referenceEvents.length ? referenceEvents.map((event, index) => (
            <article key={`${event.type}-${index}`}>
              <strong>{labelForRag(event.type)}</strong>
              <span>{referenceEventText(event)}</span>
            </article>
          )) : <p className="muted">启动后会展示资料搜集、资料理解和注入 Story Brief 的过程；完成后自动折叠为参考依据卡片。</p>}
        </div>
      </section>
      <section className="stage-run-card wide">
        <h3><FileText size={15} />Story Brief 定稿</h3>
        <textarea
          className="story-brief-approval-editor"
          disabled={!approvalPending}
          value={approvalDraft || '等待创作立项阶段输出项目定位、核心卖点、人物/世界观种子、长线伏笔、结局方向和风险提示。'}
          onChange={(event) => onApprovalDraftChange(event.target.value)}
        />
        <div className="approval-action-row">
          <p className="muted">{approvalPending ? '这是唯一默认人工闸门。你可以编辑后确认，确认稿会写入 Story Bible 并约束后续流水线。' : 'Story Brief 已定稿，后续梗概、大纲、细纲和正文会读取这份确认稿。'}</p>
          <div>
            <button className="ghost tiny-action" disabled={!approvalPending} onClick={onRegenerateBrief} type="button"><RefreshCw size={13} />换一版</button>
            <button className="tech-button" disabled={!approvalPending || !approvalDraft.trim()} onClick={() => onApproveBrief(approvalDraft)} type="button"><CheckCircle2 size={14} />确认定稿</button>
          </div>
        </div>
      </section>
    </div>
  );
}

export function PlanningStageView({ title, sections, result }: { title: string; sections: string[]; result: string }) {
  return (
    <div className="stage-run-grid">
      {sections.map((section) => (
        <section className="stage-run-card" key={section}>
          <h3><Boxes size={15} />{section}</h3>
          <p className="muted">运行中会从上游产物、Wiki 约束和质量阀门中提取内容。</p>
        </section>
      ))}
      <section className="stage-run-card wide">
        <h3><Activity size={15} />{title}</h3>
        <pre>{result || '该阶段启动后，思考过程、约束命中和阶段产物会在这里持续更新。'}</pre>
      </section>
    </div>
  );
}

export function DetailStageView({ stage, result }: { stage: WorkflowStage; result: string }) {
  const count = Number(stage.input_schema.find((field) => field.key === 'chapter_count')?.default ?? 6);
  return (
    <div className="chapter-outline-board">
      {Array.from({ length: Math.min(12, count) }, (_, index) => (
        <article key={index}>
          <strong>第{index + 1}章</strong>
          <span>目标 / 冲突 / 伏笔 / 章末钩子</span>
        </article>
      ))}
      <section className="stage-run-card wide">
        <h3><ListChecks size={15} />章节细纲输出</h3>
        <pre>{result || '章节细纲会按目标章节逐章生成，并校验是否覆盖全部章节。'}</pre>
      </section>
    </div>
  );
}

export function WritingStageView({ events, workflow }: { events: RunEvent[]; workflow: WorkflowDefinition }) {
  const chapters = chaptersFrom(events);
  const current = currentChapter(events);
  const content = writingContent(events);
  const variants = events.filter((event) => event.type === 'variant_generated' && event.chapter).slice(0, 8);
  const selected = events.filter((event) => event.type === 'best_variant_selected' && event.chapter).slice(0, 6);
  return (
    <>
      <div className="chapter-strip">
        {chapters.map((chapter) => (
          <article className={`${chapter.status} ${chapterQualityClass(events, chapter.chapter)}`} key={chapter.chapter}>
            <strong>{chapter.chapter}</strong>
            <span>{chapter.words} 字 · Q {chapter.quality_score ? chapter.quality_score.toFixed(2) : '-'} · {chapterQualityLabel(events, chapter.chapter)}</span>
          </article>
        ))}
      </div>
      <article className="writing-editor">
        <div className="writing-editor-toolbar">
          <span><BookOpenText size={14} />实时写入</span>
          <span>{current ? `${current} 正在汇入正文` : `等待正文事件 · ${workflow.quality_mode}`}</span>
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
            {!selected.length ? <p className="muted">平衡/深度模式会显示评审择优结果。</p> : null}
          </div>
        </section>
      </div>
    </>
  );
}
