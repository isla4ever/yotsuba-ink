import { AlertTriangle, CheckCircle2, History, ImageOff, RefreshCw, Sparkles } from 'lucide-react';
import { AnimatePresence, motion } from 'motion/react';
import { useMemo, useState } from 'react';
import type { QualityMode, RunEvent, WorkflowStage } from '../contracts';
import { ManuscriptLoadingIndicator } from '../layout/ManuscriptLoadingIndicator';
import { motionTransition, motionTransitionFor } from '../lib/motion';
import { useReducedMotionPreference } from '../state/useReducedMotionPreference';
import { coverAssetFromArtifact } from './coverPresentation';
import { InfoCandidateSummary } from './InfoCandidateSummary';
import { StageCandidateHistoryDialog } from './StageCandidateHistoryDialog';
import { currentDraftCandidates, draftCandidateHistory } from './stageCandidateModel';

type Props = {
  events: RunEvent[];
  mode: QualityMode;
  onSelectDraftCandidate: (stageId: string, candidateKey: string) => void;
  stage: WorkflowStage;
};

export function StageCandidateCompare({ events, mode, onSelectDraftCandidate, stage }: Props) {
  const reducedMotion = useReducedMotionPreference();
  const [historyOpen, setHistoryOpen] = useState(false);
  const candidates = useMemo(() => currentDraftCandidates(events, stage.id), [events, stage.id]);
  const history = useMemo(() => draftCandidateHistory(events, stage.id), [events, stage.id]);
  const cover = stage.type === 'cover_image';
  const info = stage.type === 'info_recommend';
  return (
    <section className={`variant-compare-focus draft-candidate-focus mode-${mode}${cover ? ' cover-draft-focus' : ''}${info ? ' info-draft-focus' : ''}`}>
      <div className="variant-compare-head">
        <span><RefreshCw size={16} />换一稿候选</span>
        <div>
          <button className="ghost tiny-action" disabled={!history.length} onClick={() => setHistoryOpen(true)} type="button">
            <History size={13} />历史候选 {history.length}
          </button>
          <b>最多 3 栏 · 手动选择</b>
        </div>
      </div>
      <div className={`variant-compare-grid count-${Math.max(1, candidates.length)}`}>
        {!candidates.length ? (
          <div className="candidate-batch-state" role="status">
            <ManuscriptLoadingIndicator size="compact" />
            <strong>候选正在生成</strong>
            <span>本轮尚未收到候选数量与内容事件。</span>
          </div>
        ) : null}
        {candidates.map((candidate) => (
          <motion.article
            animate={{ opacity: 1, y: 0 }}
            className={candidate.status}
            initial={reducedMotion ? false : { opacity: 0, y: 10 }}
            key={candidate.id}
            transition={motionTransitionFor(reducedMotion, motionTransition.standard)}
          >
            <small>{candidate.label}</small>
            <strong>{candidate.title || stage.label}</strong>
            {cover ? (
              <CoverCandidateAsset artifact={candidate.artifact} preview={candidate.preview} status={candidate.status} />
            ) : candidate.status === 'failed' ? (
              <div className="candidate-error-state" role="status"><AlertTriangle size={16} />{candidate.preview}</div>
            ) : info ? (
              <InfoCandidateSummary artifact={candidate.artifact} fallbackPreview={candidate.preview} stage={stage} />
            ) : (
              <div className="candidate-stream-copy">
                {candidate.preview.split(/\n{2,}|\n/).filter(Boolean).map((line, lineIndex) => (
                  <motion.p
                    animate={{ opacity: 1, y: 0 }}
                    initial={reducedMotion ? false : { opacity: 0, y: 5 }}
                    key={`${candidate.id}-${lineIndex}`}
                    transition={motionTransitionFor(reducedMotion, { ...motionTransition.fast, delay: lineIndex * 0.03 })}
                  >
                    {line}
                  </motion.p>
                ))}
                {candidate.status === 'generating' ? <span className="writing-caret-tail" /> : null}
              </div>
            )}
            <button className="tech-button" disabled={!candidate.ready} onClick={() => onSelectDraftCandidate(stage.id, candidate.id)} type="button">
              <CheckCircle2 size={14} />选为当前稿
            </button>
          </motion.article>
        ))}
      </div>
      <div className="variant-compare-liquid">
        <Sparkles size={16} />
        <p>选好一稿后，点击「确认定稿」即可继续。</p>
      </div>
      <AnimatePresence>
      {historyOpen ? (
        <StageCandidateHistoryDialog
          candidates={history}
          onClose={() => setHistoryOpen(false)}
          onSelect={(candidateId) => onSelectDraftCandidate(stage.id, candidateId)}
          stage={stage}
        />
      ) : null}
      </AnimatePresence>
    </section>
  );
}

function CoverCandidateAsset({ artifact, preview, status }: { artifact: unknown; preview: string; status: 'failed' | 'generating' | 'ready' }) {
  const [loadFailed, setLoadFailed] = useState(false);
  const asset = coverAssetFromArtifact(artifact);
  if (status === 'generating') {
    return <div className="cover-candidate-asset generating" role="status"><ManuscriptLoadingIndicator size="compact" /><strong>图片候选生成中</strong><span>{preview}</span></div>;
  }
  if (status === 'failed') {
    return <div className="cover-candidate-asset failed" role="status"><AlertTriangle size={22} /><strong>候选未通过结构检查</strong><span>{preview}</span></div>;
  }
  return (
    <div className="cover-candidate-visual">
      {asset.imageUrl && !loadFailed ? (
        <img alt={`${asset.title || '候选'}封面预览`} onError={() => setLoadFailed(true)} src={asset.imageUrl} />
      ) : (
        <div className="cover-candidate-asset missing" role="status">
          <ImageOff size={24} />
          <strong>{loadFailed ? '图片资产加载失败' : '图片资产尚未生成'}</strong>
          <span>{asset.composition || preview}</span>
          {asset.palette ? <small>{asset.palette}</small> : null}
        </div>
      )}
    </div>
  );
}
