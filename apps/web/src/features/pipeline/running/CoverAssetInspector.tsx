import { AlertTriangle, CheckCircle2, CircleDashed, FilePenLine, Image, ImageOff, RefreshCw } from 'lucide-react';
import { ButtonLoadingIndicator } from '../layout/ButtonLoadingIndicator';
import { LoadingButton } from '../layout/LoadingButton';
import type { CoverDeliveryCheck } from './coverPresentation';
import { coverCandidateStatusLabel, coverImageSource } from './coverPresentation';
import type { CoverArtifact } from './stageArtifacts';

type Props = {
  artifact: CoverArtifact;
  candidate: CoverArtifact['candidates'][number];
  checks: CoverDeliveryCheck[];
  formal: boolean;
  label: string;
  onEditBrief: () => void;
  onRetry: () => void;
  onSelectFormal: () => void;
  previewReady: boolean;
  readOnly: boolean;
  retryError: string;
  retrying: boolean;
};

export function CoverAssetInspector({
  artifact,
  candidate,
  checks,
  formal,
  label,
  onEditBrief,
  onRetry,
  onSelectFormal,
  previewReady,
  readOnly,
  retryError,
  retrying,
}: Props) {
  const hasSource = Boolean(coverImageSource(candidate.image_url));
  const readyCount = checks.filter((check) => check.ready).length;
  return (
    <aside aria-label="封面资产 Inspector" className="cover-asset-inspector">
      <header className="cover-asset-inspector-head">
        <div><span><Image size={14} />资产决策</span><strong>{label}</strong></div>
        <small>{formal ? '正式' : '预览'}</small>
      </header>

      <section className="cover-asset-selection-state">
        {candidate.asset_status === 'generating' ? <ButtonLoadingIndicator size="medium" /> : candidate.asset_status === 'failed' || candidate.asset_status === 'blocked' ? <AlertTriangle size={17} /> : formal ? <CheckCircle2 size={17} /> : hasSource ? <CircleDashed size={17} /> : <ImageOff size={17} />}
        <div><strong>{formal ? '当前正式封面' : coverCandidateStatusLabel(candidate.asset_status)}</strong><span>{candidate.error_message || candidate.quality_summary || '暂无候选质量说明'}</span></div>
      </section>

      {!readOnly && ['failed', 'blocked'].includes(candidate.asset_status) ? (
        <LoadingButton className="cover-asset-retry" loading={retrying} loadingLabel="正在重试" onClick={onRetry}>
          <RefreshCw size={14} />重试该候选
        </LoadingButton>
      ) : null}
      {retryError ? <p className="cover-asset-retry-error" role="alert">{retryError}</p> : null}

      {!readOnly ? (
        <button className="mode-primary-action cover-formal-action" disabled={formal || !hasSource || !previewReady} onClick={onSelectFormal} type="button">
          <CheckCircle2 size={14} />{formal ? '已是正式封面' : '设为正式封面'}
        </button>
      ) : null}

      <section className="cover-creative-brief">
        <header><span>创作简报</span><button onClick={onEditBrief} type="button"><FilePenLine size={13} />{readOnly ? '查看' : '编辑'}</button></header>
        <p>{artifact.copy_suggestions[0] || artifact.brief}</p>
        <div>{artifact.visual_keywords.map((keyword) => <span key={keyword}>{keyword}</span>)}</div>
      </section>

      <section className="cover-delivery-status">
        <header><span>交付准备</span><strong>{readyCount}/{checks.length}</strong></header>
        <div className="cover-delivery-ledger">
          {checks.map((check) => (
            <span className={check.ready ? 'ready' : 'missing'} key={check.key} title={check.detail}>
              {check.ready ? <CheckCircle2 size={12} /> : <CircleDashed size={12} />}<b>{check.label}</b>
            </span>
          ))}
        </div>
      </section>
    </aside>
  );
}
