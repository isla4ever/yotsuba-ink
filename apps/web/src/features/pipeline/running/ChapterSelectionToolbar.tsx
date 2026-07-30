import { Expand, LocateFixed, Minimize2, Paintbrush, RefreshCw, WandSparkles, X } from 'lucide-react';
import { useState } from 'react';
import type { ChapterQualityRepairTarget, ChapterRevisionOperation, ChapterSelection } from '../contracts';

type Props = {
  busy: boolean;
  error: string;
  repairTarget?: ChapterQualityRepairTarget;
  selection: ChapterSelection;
  onCancelRepair?: () => void;
  onClearError: () => void;
  onGenerate: (operation: ChapterRevisionOperation, direction: string) => void;
};

const operations: Array<{
  key: ChapterRevisionOperation;
  label: string;
  icon: typeof RefreshCw;
}> = [
  { key: 'rewrite', label: '重写', icon: RefreshCw },
  { key: 'expand', label: '扩写', icon: Expand },
  { key: 'compress', label: '压缩', icon: Minimize2 },
  { key: 'restyle', label: '换风格', icon: Paintbrush },
];

export function ChapterSelectionToolbar({
  busy,
  error,
  repairTarget,
  selection,
  onCancelRepair,
  onClearError,
  onGenerate,
}: Props) {
  const [direction, setDirection] = useState('');
  const repairOperation = repairTarget ? operations.find((item) => item.key === repairTarget.operation) : undefined;
  return (
    <section aria-busy={busy} aria-label="正文选区工具" className={`chapter-selection-toolbar${repairTarget ? ' quality-repair-command' : ''}`}>
      <div className="chapter-selection-summary">
        <strong>{repairTarget ? <><LocateFixed size={11} />质量定位 · {repairTarget.message}</> : `已选 ${selection.text.length} 字`}</strong>
        <span>{selection.text.replace(/\s+/g, ' ').slice(0, 42)}</span>
      </div>
      {repairTarget ? <p>{repairTarget.instruction}</p> : (
        <input
          aria-label="局部修订补充要求"
          disabled={busy}
          maxLength={500}
          onChange={(event) => {
            setDirection(event.target.value);
            if (error) onClearError();
          }}
          placeholder="补充要求（换风格时建议填写）"
          value={direction}
        />
      )}
      <div className="chapter-selection-actions">
        {repairTarget ? (
          <>
            <button disabled={busy} onClick={onCancelRepair} title="取消本次质量定位" type="button"><X size={13} /><span>取消</span></button>
            <button className="primary" disabled={busy} onClick={() => onGenerate(repairTarget.operation, repairTarget.instruction)} type="button">
              <WandSparkles size={13} /><span>生成{repairOperation?.label ?? '修订'}候选</span>
            </button>
          </>
        ) : operations.map(({ key, label, icon: Icon }) => (
          <button
            disabled={busy || (key === 'restyle' && !direction.trim())}
            key={key}
            onClick={() => onGenerate(key, direction)}
            title={key === 'restyle' && !direction.trim() ? '请先填写目标风格' : `${label}所选正文`}
            type="button"
          >
            <Icon aria-hidden="true" size={13} />
            <span>{label}</span>
          </button>
        ))}
      </div>
      {error ? <p className="chapter-revision-error" role="alert">{error}</p> : null}
    </section>
  );
}
