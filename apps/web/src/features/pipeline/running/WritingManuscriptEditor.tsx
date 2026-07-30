import { ArrowDownToLine, BookOpenText, Check, FilePenLine, LockKeyhole } from 'lucide-react';
import type { MutableRefObject } from 'react';
import type {
  ChapterQualityRepairTarget,
  ChapterRevisionOperation,
  ChapterSelection,
  WorkflowDefinition,
} from '../contracts';
import type { StreamRevealPace } from '../lib/streamText';
import { creationModeTitle } from '../lib/terminology';
import { ChapterSelectionToolbar } from './ChapterSelectionToolbar';
import { StreamingProse, StreamingSkeleton } from './StreamingProse';
import type { WritingChapter, WritingReadiness } from './writingArtifactModel';
import type { ManuscriptReaderElement } from './writingViewport';

type Props = {
  chapter: WritingChapter;
  dirty: boolean;
  editorLocked: boolean;
  followingStream: boolean;
  onCancelRepair: () => void;
  onCaptureSelection: (target: HTMLTextAreaElement) => void;
  onChange: (target: HTMLTextAreaElement) => void;
  onClearRevisionError: () => void;
  onGenerateRevision: (operation: ChapterRevisionOperation, direction: string) => void;
  onResumeStream: () => void;
  onScroll: (target: ManuscriptReaderElement) => void;
  qualityRepairTarget: ChapterQualityRepairTarget | null;
  readOnly: boolean;
  readerRef: MutableRefObject<ManuscriptReaderElement | null>;
  readiness: WritingReadiness;
  repairError: string;
  revisionBusy: boolean;
  revisionError: string;
  selection: ChapterSelection | null;
  streaming: boolean;
  streamPace: StreamRevealPace;
  visibleText: string;
  workflow: WorkflowDefinition;
};

export function WritingManuscriptEditor({
  chapter,
  dirty,
  editorLocked,
  followingStream,
  onCancelRepair,
  onCaptureSelection,
  onChange,
  onClearRevisionError,
  onGenerateRevision,
  onResumeStream,
  onScroll,
  qualityRepairTarget,
  readOnly,
  readerRef,
  readiness,
  repairError,
  revisionBusy,
  revisionError,
  selection,
  streaming,
  streamPace,
  visibleText,
  workflow,
}: Props) {
  return (
    <article className="writing-editor writing-editor-phase85">
      <header className="writing-editor-toolbar">
        <div>
          <BookOpenText aria-hidden="true" size={15} />
          <span><strong>{chapter.generated_title || chapter.title}</strong><small>{chapter.title} · {chapter.words.toLocaleString()} 字</small></span>
        </div>
        <div className="writing-save-state" title={editorLocked ? '当前稿件不可编辑' : '人工编辑会保留在当前待定稿版本'}>
          {editorLocked ? <LockKeyhole size={13} /> : dirty ? <FilePenLine size={13} /> : <Check size={13} />}
          <span>{streaming ? '正在写入' : readOnly ? '已定稿' : dirty ? '当前阶段有修改' : `v${chapter.version} 已保存`}</span>
        </div>
      </header>
      <div className="chapter-selection-slot chapter-selection-slot-phase85">
        {selection && !editorLocked ? (
          <ChapterSelectionToolbar
            busy={revisionBusy}
            error={revisionError || repairError}
            onCancelRepair={onCancelRepair}
            onClearError={onClearRevisionError}
            onGenerate={onGenerateRevision}
            repairTarget={qualityRepairTarget ?? undefined}
            selection={selection}
          />
        ) : repairError ? <p className="chapter-repair-stale" role="alert">{repairError}</p> : null}
      </div>
      {streaming ? (
        <div
          aria-label={`${chapter.title}正文`}
          className="writing-manuscript writing-manuscript-streaming"
          onScroll={(event) => onScroll(event.currentTarget)}
          ref={(node) => { readerRef.current = node; }}
          tabIndex={0}
        >
          {visibleText
            ? <StreamingProse pace={streamPace} text={visibleText} />
            : <StreamingSkeleton label="正在等待首段正文" />}
        </div>
      ) : (
        <textarea
          aria-label={`${chapter.title}正文`}
          className="writing-manuscript"
          onChange={(event) => onChange(event.currentTarget)}
          onKeyUp={(event) => onCaptureSelection(event.currentTarget)}
          onMouseUp={(event) => onCaptureSelection(event.currentTarget)}
          onScroll={(event) => onScroll(event.currentTarget)}
          onSelect={(event) => onCaptureSelection(event.currentTarget)}
          readOnly={editorLocked}
          ref={(node) => { readerRef.current = node; }}
          spellCheck={false}
          value={chapter.content}
        />
      )}
      {streaming && !followingStream ? (
        <button className="writing-resume-stream" onClick={onResumeStream} type="button">
          <ArrowDownToLine size={13} />回到生成位置
        </button>
      ) : null}
      <footer className="writing-editor-status">
        <span>{creationModeTitle(workflow.quality_mode)}模式</span>
        <span className={readiness.ready ? 'ready' : 'pending'}>{readiness.ready ? '必填内容完整' : `待补 ${readiness.missingLabels.length} 项`}</span>
      </footer>
    </article>
  );
}
