import { useEffect, useMemo, useState } from 'react';
import { retryCoverAsset } from '../services/runApi';
import { CoverAssetInspector } from './CoverAssetInspector';
import { CoverAssetPreview } from './CoverAssetPreview';
import { CoverBriefDialog } from './CoverBriefDialog';
import { CoverCandidateRail } from './CoverCandidateRail';
import {
  coverCandidateLabel,
  coverDeliveryChecks,
  formalCoverCandidateId,
  coverImageSource,
} from './coverPresentation';
import { StageToast } from './StageToast';
import { coverArtifact, type CoverArtifact } from './stageArtifacts';

type Props = {
  activeRunId: string;
  onArtifactChange?: (artifact: CoverArtifact) => void;
  readOnly?: boolean;
  result: string;
};

export function CoverStageView({ activeRunId, onArtifactChange, readOnly = false, result }: Props) {
  const artifact = coverArtifact(result);
  const [previewId, setPreviewId] = useState(() => initialPreviewId(artifact));
  const [previewReady, setPreviewReady] = useState(false);
  const [briefOpen, setBriefOpen] = useState(false);
  const [toast, setToast] = useState('');
  const [retryingId, setRetryingId] = useState('');
  const [retryError, setRetryError] = useState('');

  useEffect(() => {
    if (!artifact.candidates.some((candidate) => candidate.id === previewId)) {
      setPreviewId(initialPreviewId(artifact));
    }
  }, [artifact, previewId]);

  const previewIndex = Math.max(0, artifact.candidates.findIndex((candidate) => candidate.id === previewId));
  const preview = artifact.candidates[previewIndex];
  const checks = useMemo(() => coverDeliveryChecks(artifact), [artifact]);
  if (!preview) return <div className="stage-artifact-state invalid">封面产物未包含可用候选方案。</div>;

  const formalId = formalCoverCandidateId(artifact);
  const formal = preview.id === formalId;
  const label = coverCandidateLabel(previewIndex);
  const selectFormal = () => {
    if (!previewReady || !coverImageSource(preview.image_url)) return;
    onArtifactChange?.({ ...artifact, selected_candidate_id: preview.id });
    setToast(`${label}已设为正式封面`);
  };
  const retryCandidate = async () => {
    if (readOnly || retryingId || !['failed', 'blocked'].includes(preview.asset_status)) return;
    setRetryError('');
    setRetryingId(preview.id);
    try {
      const response = await retryCoverAsset(activeRunId, preview.id, crypto.randomUUID());
      onArtifactChange?.(coverArtifact(JSON.stringify(response.artifact)));
      setToast(response.reused ? `${label}已恢复此前保存的封面` : `${label}已完成重试`);
    } catch (error) {
      setRetryError(error instanceof Error ? error.message : '封面候选重试失败');
    } finally {
      setRetryingId('');
    }
  };

  return (
    <div className="cover-asset-workbench">
      <StageToast durationMs={1500} message={toast} onDismiss={() => setToast('')} />
      <CoverCandidateRail
        candidates={artifact.candidates}
        formalId={formalId}
        onPreview={(candidateId) => { setPreviewReady(false); setPreviewId(candidateId); }}
        previewId={preview.id}
      />
      <CoverAssetPreview candidate={preview} formal={formal} label={label} onAssetState={setPreviewReady} />
      <CoverAssetInspector
        artifact={artifact}
        candidate={preview}
        checks={checks}
        formal={formal}
        label={label}
        onEditBrief={() => setBriefOpen(true)}
        onRetry={retryCandidate}
        onSelectFormal={selectFormal}
        previewReady={previewReady}
        readOnly={readOnly}
        retryError={retryError}
        retrying={retryingId === preview.id}
      />
      {briefOpen ? (
        <CoverBriefDialog
          artifact={artifact}
          onClose={() => setBriefOpen(false)}
          onSave={(draft) => {
            onArtifactChange?.({ ...artifact, ...draft });
            setBriefOpen(false);
            setToast('封面生成简报已保存到当前稿');
          }}
          readOnly={readOnly}
        />
      ) : null}
    </div>
  );
}

function initialPreviewId(artifact: CoverArtifact) {
  return artifact.candidates.some((candidate) => candidate.id === artifact.selected_candidate_id)
    ? artifact.selected_candidate_id
    : artifact.candidates[0]?.id ?? '';
}
