import { BookOpenText, Edit3, Eye } from 'lucide-react';
import { motion } from 'motion/react';
import { useEffect, useMemo, useState } from 'react';
import type { QualityMode } from '../contracts';
import { motionTransition, motionTransitionFor } from '../lib/motion';
import { splitStreamingLines } from '../lib/streamText';
import { useReducedMotionPreference } from '../state/useReducedMotionPreference';
import { useStreamReveal } from '../state/useStreamReveal';
import type { SummaryArtifact } from './stageArtifacts';
import { StreamingSkeleton } from './StreamingProse';
import { SummaryNarrativeCommitments } from './SummaryNarrativeCommitments';

type Props = {
  artifact: SummaryArtifact;
  deltas: Array<{ section: string; delta: string }>;
  generating: boolean;
  onArtifactChange: (patch: Partial<SummaryArtifact>) => void;
  onDraftSaved?: (message: string) => void;
  qualityMode: QualityMode;
  readOnly: boolean;
  sourceKey: string;
};

export function SummaryManuscriptPane({ artifact, deltas, generating, onArtifactChange, onDraftSaved, qualityMode, readOnly, sourceKey }: Props) {
  const reducedMotion = useReducedMotionPreference();
  const [editing, setEditing] = useState(false);
  const deltaText = useMemo(() => deltas.map((item) => item.delta).join('\n'), [deltas]);
  const streamSource = generating && deltaText ? deltaText : artifact.full_synopsis;
  const { text: visibleSynopsis } = useStreamReveal(streamSource, {
    active: Boolean(generating && deltaText),
    mode: 'smooth',
    tickMs: 42,
  });
  const synopsisLines = useMemo(
    () => splitStreamingLines(generating ? visibleSynopsis : artifact.full_synopsis, 72),
    [artifact.full_synopsis, generating, visibleSynopsis],
  );

  useEffect(() => setEditing(false), [readOnly, sourceKey]);

  return (
    <section className={`summary-manuscript-pane ${editing ? 'is-editing' : 'is-reading'}`}>
      <div className="summary-pane-head summary-manuscript-head">
        <div>
          <p className="eyebrow">主稿</p>
          <h3><BookOpenText size={15} />完整梗概</h3>
        </div>
        {!readOnly && !generating ? (
          <button
            aria-pressed={editing}
            className="summary-manuscript-mode"
            onClick={() => setEditing((value) => !value)}
            type="button"
          >
            {editing ? <Eye size={14} /> : <Edit3 size={14} />}
            {editing ? '返回阅读' : '编辑主稿'}
          </button>
        ) : null}
      </div>
      <div className="summary-manuscript-editor">
        <div aria-live={generating ? 'polite' : undefined} className={`summary-stream-paper ${generating ? 'streaming' : editing ? 'editing' : 'settled'}`}>
          {generating ? (
            synopsisLines.length ? synopsisLines.map((line, index, lines) => (
              <motion.p
                animate={{ opacity: 1, y: 0, filter: 'blur(0px)' }}
                className="smooth-writing-line"
                initial={reducedMotion ? false : { opacity: 0, y: 6, filter: 'blur(3px)' }}
                key={`${index}-${line.slice(0, 18)}`}
                transition={motionTransitionFor(reducedMotion, motionTransition.fast)}
              >
                {line}{index === lines.length - 1 ? <span className="writing-caret-tail" /> : null}
              </motion.p>
            )) : <StreamingSkeleton label="正在读取 Info 定稿、人物关系和世界观约束" />
          ) : editing ? (
            <textarea
              aria-label="编辑完整梗概"
              autoFocus
              className="summary-paper-editor"
              onChange={(event) => onArtifactChange({ full_synopsis: event.target.value })}
              value={artifact.full_synopsis}
            />
          ) : (
            <div className="summary-paper-readable" aria-label="完整梗概正文">
              {synopsisLines.length
                ? synopsisLines.map((line, index) => <p key={`${index}-${line.slice(0, 20)}`}>{line}</p>)
                : <p className="writing-empty">完整梗概尚未生成。</p>}
            </div>
          )}
        </div>
      </div>
      <SummaryNarrativeCommitments
        artifact={artifact}
        onChange={(patch) => {
          onArtifactChange(patch);
          onDraftSaved?.('叙事承诺已保存到当前稿，定稿后写回');
        }}
        qualityMode={qualityMode}
        readOnly={readOnly}
      />
    </section>
  );
}
