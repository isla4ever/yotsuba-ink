import { ImageOff } from 'lucide-react';
import { useEffect, useState } from 'react';
import { useReducedMotionPreference } from '../state/useReducedMotionPreference';
import { ButtonLoadingIndicator } from '../layout/ButtonLoadingIndicator';
import { ManuscriptLoadingIndicator } from '../layout/ManuscriptLoadingIndicator';
import { coverImageSource } from './coverPresentation';
import type { CoverArtifact } from './stageArtifacts';

type CoverCandidate = CoverArtifact['candidates'][number];

type Props = {
  candidate: CoverCandidate;
  formal: boolean;
  label: string;
  onAssetState: (ready: boolean) => void;
};

export function CoverAssetPreview({ candidate, formal, label, onAssetState }: Props) {
  const source = coverImageSource(candidate.image_url);
  const reducedMotion = useReducedMotionPreference();
  const [visibleSource, setVisibleSource] = useState('');
  const [pendingSource, setPendingSource] = useState(source);
  const [previousSource, setPreviousSource] = useState('');
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    setFailed(false);
    if (!source) {
      setVisibleSource('');
      setPendingSource('');
      setPreviousSource('');
      onAssetState(false);
      return;
    }
    if (source === visibleSource) {
      setPendingSource('');
      onAssetState(true);
      return;
    }
    setPendingSource(source);
    onAssetState(false);
  }, [source, visibleSource, onAssetState]);

  const reveal = () => {
    setPreviousSource(reducedMotion ? '' : visibleSource);
    setVisibleSource(pendingSource);
    setPendingSource('');
    onAssetState(true);
  };
  const fail = () => {
    setFailed(true);
    setVisibleSource('');
    setPendingSource('');
    setPreviousSource('');
    onAssetState(false);
  };

  return (
    <main aria-label={`${label}封面预览`} className="cover-asset-preview">
      <header><span>{formal ? '正式封面' : '候选预览'}</span><strong>{label}</strong></header>
      <div aria-busy={Boolean(pendingSource)} className="cover-asset-canvas">
        {visibleSource || previousSource || pendingSource ? (
          <div className="cover-image-frame">
            <div className="cover-image-stage">
              {previousSource ? <img alt="" className="cover-decoded-image outgoing" onAnimationEnd={() => setPreviousSource('')} src={previousSource} /> : null}
              {visibleSource ? <img alt={`${label}封面`} className="cover-decoded-image current" src={visibleSource} /> : null}
              {pendingSource ? <img alt="" className="cover-decoded-image decoding" onError={fail} onLoad={reveal} src={pendingSource} /> : null}
            </div>
          </div>
        ) : null}
        {!visibleSource && !pendingSource ? <CoverAssetEmpty candidate={candidate} decodeFailed={failed} /> : null}
        {pendingSource ? <span className="cover-asset-decoding"><ButtonLoadingIndicator />正在解码图片资产</span> : null}
      </div>
      <footer><span>{candidate.composition || '构图待补充'}</span><small>{candidate.palette || '色板待补充'}</small></footer>
    </main>
  );
}

function CoverAssetEmpty({ candidate, decodeFailed }: { candidate: CoverCandidate; decodeFailed: boolean }) {
  const generating = candidate.asset_status === 'generating';
  const failed = decodeFailed || candidate.asset_status === 'failed' || candidate.asset_status === 'blocked';
  return (
    <div className="cover-asset-empty phase86" role="status">
      {generating ? <ManuscriptLoadingIndicator size="compact" /> : <ImageOff size={30} />}
      <strong>{generating ? '正在生成真实图片' : failed ? decodeFailed ? '图片资产无法解码' : '图片候选生成失败' : '图片资产等待生成'}</strong>
      <span>{generating ? '构图和色板已经锁定，图片生成完成后会显示预览。' : failed ? candidate.error_message || '可以在资产决策区重试该候选。' : '构图方案已经保留，等待图片服务生成封面。'}</span>
    </div>
  );
}
