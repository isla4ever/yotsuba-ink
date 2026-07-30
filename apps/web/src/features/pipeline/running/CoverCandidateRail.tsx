import { AlertTriangle, CheckCircle2, CircleDashed, ImageOff, ShieldAlert } from 'lucide-react';
import { useEffect, useState } from 'react';
import { ButtonLoadingIndicator } from '../layout/ButtonLoadingIndicator';
import { coverCandidateLabel, coverCandidateStatusLabel, coverImageSource } from './coverPresentation';
import type { CoverArtifact } from './stageArtifacts';

type CoverCandidate = CoverArtifact['candidates'][number];

type Props = {
  candidates: CoverCandidate[];
  formalId: string;
  onPreview: (candidateId: string) => void;
  previewId: string;
};

export function CoverCandidateRail({ candidates, formalId, onPreview, previewId }: Props) {
  return (
    <aside aria-label="封面候选方案" className="cover-asset-rail">
      <header><span>候选方案</span><strong>{candidates.length}</strong></header>
      <div className="cover-asset-rail-list">
        {candidates.map((candidate, index) => (
          <CoverCandidateButton
            candidate={candidate}
            formal={candidate.id === formalId}
            index={index}
            key={candidate.id || index}
            onPreview={() => onPreview(candidate.id)}
            previewed={candidate.id === previewId}
          />
        ))}
      </div>
    </aside>
  );
}

function CoverCandidateButton({ candidate, formal, index, onPreview, previewed }: {
  candidate: CoverCandidate;
  formal: boolean;
  index: number;
  onPreview: () => void;
  previewed: boolean;
}) {
  const source = coverImageSource(candidate.image_url);
  const [failed, setFailed] = useState(false);
  const label = coverCandidateLabel(index);

  useEffect(() => setFailed(false), [source]);

  return (
    <button aria-label={`预览${label}${formal ? '，当前正式封面' : ''}`} aria-pressed={previewed} className={`cover-candidate-sheet${previewed ? ' active' : ''}`} onClick={onPreview} type="button">
      <span className="cover-candidate-visual">
        <span className="cover-asset-thumb">
          {source && !failed ? <img alt="" onError={() => setFailed(true)} src={source} /> : <ImageOff aria-hidden="true" size={17} />}
        </span>
        <span className="cover-asset-rail-copy"><strong>{label}</strong><small>{coverCandidateStatusLabel(candidate.asset_status)}</small></span>
        <CandidateStatusIcon status={candidate.asset_status} />
        {formal ? <CheckCircle2 aria-label="正式封面" className="cover-asset-formal-mark" size={14} /> : null}
      </span>
    </button>
  );
}

function CandidateStatusIcon({ status }: { status: CoverCandidate['asset_status'] }) {
  if (status === 'generating') return <span aria-label="正在生成" className="cover-candidate-status" role="status"><ButtonLoadingIndicator /></span>;
  if (status === 'ready') return <CheckCircle2 aria-label="资产就绪" className="cover-candidate-status ready" size={13} />;
  if (status === 'failed') return <AlertTriangle aria-label="生成失败" className="cover-candidate-status failed" size={13} />;
  if (status === 'blocked') return <ShieldAlert aria-label="需人工处理" className="cover-candidate-status failed" size={13} />;
  return <CircleDashed aria-label="等待生成" className="cover-candidate-status" size={13} />;
}
