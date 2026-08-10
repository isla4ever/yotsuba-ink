import { Check, Image, ImageOff, LoaderCircle, Palette, ShieldAlert } from 'lucide-react';
import { useEffect, useMemo, useState } from 'react';
import type { CoverAssetRecord } from '../contracts';
import { coverAssetUrl, getCoverAssets } from '../services/coverAssetApi';
import { parseCoverArtifact, type CoverArtifactVnext } from './artifactsVnext';
import { VnextArtifactError } from './VnextArtifactError';

type Props = {
  onArtifactChange: (artifact: CoverArtifactVnext) => void;
  readOnly: boolean;
  result: string;
  runId: string;
  sourceResult: string;
};

export function CoverStageViewVnext({ onArtifactChange, readOnly, result, runId, sourceResult }: Props) {
  const parsed = useMemo(() => parseCoverArtifact(result), [result]);
  const [artifact, setArtifact] = useState<CoverArtifactVnext | null>(parsed.artifact);
  const [assets, setAssets] = useState<CoverAssetRecord[]>([]);
  const [assetState, setAssetState] = useState<'loading' | 'ready' | 'error'>('loading');
  useEffect(() => { if (parsed.artifact) setArtifact(parsed.artifact); }, [parsed.artifact]);
  useEffect(() => {
    if (!runId) return undefined;
    const controller = new AbortController();
    setAssetState('loading');
    void getCoverAssets(runId, controller.signal)
      .then((collection) => {
        setAssets(collection.items);
        setAssetState('ready');
      })
      .catch((error: unknown) => {
        if (error instanceof DOMException && error.name === 'AbortError') return;
        setAssetState('error');
      });
    return () => controller.abort();
  }, [runId, sourceResult]);
  if (!artifact) return <VnextArtifactError errors={parsed.errors} label="Cover Artifact" />;
  const update = (next: CoverArtifactVnext) => { setArtifact(next); onArtifactChange(next); };
  const preview = assets.find((item) => item.asset_id === artifact.selected_asset_id) ?? assets[0];
  const briefReadOnly = readOnly || Boolean(runId) && (assetState !== 'ready' || assets.length > 0);
  return (
    <div className="vnext-artifact-workbench cover-vnext">
      <section className="vnext-cover-gallery">
        <header>
          <div><span>封面候选</span><strong>{artifact.selected_asset_id ? <Check size={15} /> : <ImageOff size={15} />}{artifact.selected_asset_id ? '已选正式封面' : '待选择'}</strong></div>
          <span className={`vnext-cover-asset-state ${assetState}`}>
            {assetState === 'loading' ? <LoaderCircle size={14} /> : assetState === 'error' ? <ShieldAlert size={14} /> : <Image size={14} />}
            {assetState === 'loading' ? '读取中' : assetState === 'error' ? '资产不可用' : `${assets.length} 张`}
          </span>
        </header>
        <div className="vnext-cover-preview">
          {preview ? <img alt="当前封面候选" src={coverAssetUrl(runId, preview.asset_id)} /> : <ImageOff aria-hidden="true" size={28} />}
        </div>
        <div aria-label="封面候选" className="vnext-cover-candidate-rail" role="list">
          {assets.map((asset) => {
            const selected = artifact.selected_asset_id === asset.asset_id;
            return (
              <button
                aria-pressed={selected}
                className={selected ? 'selected' : ''}
                disabled={readOnly}
                key={asset.asset_id}
                onClick={() => update({ ...artifact, selected_asset_id: asset.asset_id })}
                title={`选择候选 ${asset.candidate_index}`}
                type="button"
              >
                <img alt="" src={coverAssetUrl(runId, asset.asset_id)} />
                <span>{String(asset.candidate_index).padStart(2, '0')}</span>
                {selected ? <Check size={14} /> : null}
              </button>
            );
          })}
        </div>
      </section>
      <section className="vnext-artifact-section vnext-cover-brief">
        <header><div><Palette size={15} /><span>视觉 Brief</span><strong>{briefReadOnly && !readOnly ? '候选已绑定' : `${artifact.brief.palette.length} 色`}</strong></div></header>
        <label className="vnext-field"><span>核心概念</span><textarea onChange={(event) => update({ ...artifact, brief: { ...artifact.brief, concept: event.target.value } })} readOnly={briefReadOnly} rows={4} value={artifact.brief.concept} /></label>
        <label className="vnext-field"><span>画面指令</span><textarea onChange={(event) => update({ ...artifact, brief: { ...artifact.brief, image_prompt: event.target.value } })} readOnly={briefReadOnly} rows={9} value={artifact.brief.image_prompt} /></label>
        <div className="vnext-field-grid">
          <label className="vnext-field"><span>色彩</span><textarea onChange={(event) => update({ ...artifact, brief: { ...artifact.brief, palette: lines(event.target.value) } })} readOnly={briefReadOnly} rows={4} value={artifact.brief.palette.join('\n')} /></label>
          <label className="vnext-field"><span>排除项</span><textarea onChange={(event) => update({ ...artifact, brief: { ...artifact.brief, negative_constraints: lines(event.target.value) } })} readOnly={briefReadOnly} rows={4} value={artifact.brief.negative_constraints.join('\n')} /></label>
        </div>
      </section>
    </div>
  );
}

function lines(value: string) {
  return value.split('\n').map((item) => item.trim()).filter(Boolean);
}
