import { AlertTriangle, BookOpenCheck, ChevronRight, CircleDot, FileText, LockKeyhole } from 'lucide-react';
import type { ChapterContextManifestRecord } from '../contracts';
import type { ChapterContextManifestState } from '../state/useChapterContextManifest';

type Props = ChapterContextManifestState & {
  detail?: boolean;
  onOpen?: () => void;
};

const purposeLabels: Record<string, string> = {
  chapter_script: '本章施工图',
  pov_and_scene_subjects: '本章人物范围',
  local_promise_and_closure: '本卷承诺与闭合',
  sequential_continuity: '上一章交接',
  controlling_revision_direction: '本次修订方向',
};

export function ChapterContextManifestPanel({ detail = false, onOpen, record, status, error }: Props) {
  if (status !== 'ready' || !record) {
    return (
      <section className="config-section runtime-insight-card context-manifest-panel is-unavailable" aria-live="polite">
        <ManifestHeading onOpen={onOpen} />
        <div className="context-manifest-state">
          {status === 'loading' ? <CircleDot className="is-pulsing" size={16} /> : <AlertTriangle size={16} />}
          <div>
            <strong>{status === 'loading' ? '正在读取本章上下文' : '上下文清单不可用'}</strong>
            <span>{error || '等待 Graph 写入当前章节的 Manifest 引用。'}</span>
          </div>
        </div>
      </section>
    );
  }

  const { manifest } = record;
  return (
    <section className={`config-section runtime-insight-card context-manifest-panel${detail ? ' is-detail' : ''}`}>
      <ManifestHeading chapterId={record.chapter_id} onOpen={onOpen} />
      <div className="context-manifest-metrics" aria-label="上下文预算摘要">
        <Metric label="必需来源" value={`${manifest.required.length}`} />
        <Metric label="可选来源" value={`${manifest.optional.length}`} />
        <Metric label="输入字符" value={manifest.budget.input_chars.toLocaleString()} />
        <Metric label="输出预算" value={`${manifest.budget.output_tokens.toLocaleString()} tok`} />
      </div>
      {detail ? <ManifestDetail record={record} /> : <button className="context-manifest-open" onClick={onOpen} type="button"><span>查看本章取用范围</span><ChevronRight size={14} /></button>}
    </section>
  );
}

function ManifestHeading({ chapterId, onOpen }: { chapterId?: string; onOpen?: () => void }) {
  return (
    <header className="context-manifest-heading">
      <div>
        <p className="eyebrow">正文上下文</p>
        <h3><BookOpenCheck size={15} />本章 Context Manifest</h3>
        {chapterId ? <span>{chapterId} · Graph 冻结清单</span> : null}
      </div>
      {onOpen ? <button aria-label="打开本章上下文详情" className="context-manifest-icon-button" onClick={onOpen} title="打开本章上下文详情" type="button"><FileText size={14} /></button> : null}
    </header>
  );
}

function ManifestDetail({ record }: { record: ChapterContextManifestRecord }) {
  const { manifest } = record;
  return (
    <div className="context-manifest-detail">
      <ManifestList label="必须读取" values={manifest.required} tone="required" />
      <ManifestList label="可选读取" values={manifest.optional} tone="optional" />
      <ManifestList label="明确禁止" values={manifest.forbidden} tone="forbidden" />
      <div className="context-manifest-snippets">
        <div className="context-manifest-subhead"><LockKeyhole size={13} /><span>已装配片段</span></div>
        {manifest.snippets.map((snippet) => (
          <article key={snippet.ref}>
            <strong>{purposeLabels[snippet.purpose] || snippet.purpose}</strong>
            <span>{snippetSummary(snippet.purpose, snippet.text)} · {snippet.text.length.toLocaleString()} 字符</span>
          </article>
        ))}
      </div>
      <p className="context-manifest-note">正文节点只读取这份清单；不会在生成中盲检索 Wiki、Canon 或整章历史正文。</p>
    </div>
  );
}

function ManifestList({ label, values, tone }: { label: string; values: readonly string[]; tone: string }) {
  return (
    <div className={`context-manifest-list ${tone}`}>
      <span>{label}</span>
      <div>{values.length ? values.map((value) => <code key={value}>{displaySource(value)}</code>) : <small>无</small>}</div>
    </div>
  );
}

function Metric({ label, value }: { label: string; value: string }) {
  return <div><span>{label}</span><strong>{value}</strong></div>;
}

function displaySource(value: string) {
  return value.split('.').join(' · ');
}

function snippetSummary(purpose: string, text: string) {
  const summaries: Record<string, string> = {
    chapter_script: '地点、目标、冲突、转折与结果',
    pov_and_scene_subjects: '当前 POV 与场景人物',
    local_promise_and_closure: '本卷的承诺、危机、高潮与闭合',
    sequential_continuity: '上一章留下的承接压力',
    controlling_revision_direction: '人工指定的局部修订约束',
  };
  if (summaries[purpose]) return summaries[purpose];
  return text.trim() ? '已签名的章节工作片段' : '空片段';
}
