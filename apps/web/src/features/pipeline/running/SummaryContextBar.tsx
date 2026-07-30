import { BookMarked, CircleCheck } from 'lucide-react';
import type { SummaryReadiness } from './summaryArtifactModel';

type Props = {
  generating: boolean;
  onOneLinerChange: (value: string) => void;
  oneLiner: string;
  readOnly: boolean;
  readiness: SummaryReadiness;
};

export function SummaryContextBar({ generating, onOneLinerChange, oneLiner, readOnly, readiness }: Props) {
  const status = generating
    ? '正在生成主稿'
    : readiness.ready
      ? '可作为分卷依据'
      : `待补：${readiness.missingLabels.join('、')}`;

  return (
    <section aria-label="梗概定稿上下文" className="summary-context-bar">
      <label className="summary-context-story">
        <span><BookMarked size={14} />故事核心</span>
        <input
          aria-label="故事核心"
          onChange={(event) => onOneLinerChange(event.target.value)}
          readOnly={readOnly}
          value={oneLiner}
        />
      </label>
      <div aria-label={`内容完整度 ${readiness.completed}/${readiness.total}`} className={`summary-readiness ${readiness.ready ? 'ready' : 'incomplete'}`} role="status">
        <div className="summary-readiness-heading">
          <span>{readiness.ready ? <CircleCheck size={14} /> : null}内容完整度</span>
          <strong>{readiness.completed}/{readiness.total}</strong>
        </div>
        <div aria-hidden="true" className="summary-readiness-track">
          {Array.from({ length: readiness.total }, (_, index) => (
            <i className={index < readiness.completed ? 'complete' : ''} key={index} />
          ))}
        </div>
        <small>{status}</small>
      </div>
    </section>
  );
}
