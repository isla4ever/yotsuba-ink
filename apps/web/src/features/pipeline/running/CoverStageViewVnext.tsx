import { Check, Image, ImageOff, LoaderCircle, Palette, ShieldAlert } from 'lucide-react';
import { useEffect, useMemo, useState } from 'react';
import type { CoverAssetRecord } from '../contracts';
import { coverAssetUrl, getCoverAssets } from '../services/coverAssetApi';
import { parseCoverArtifact, type CoverArtifactVnext } from './artifactsVnext';
import { PaletteSwatchField } from './PaletteSwatchField';
import { PhraseTagField } from './PhraseTagField';
import { VnextArtifactError } from './VnextArtifactError';

type Props = {
  coverAssetRequired?: boolean;
  onArtifactChange: (artifact: CoverArtifactVnext) => void;
  readOnly: boolean;
  result: string;
  runId: string;
  sourceResult: string;
};

export function CoverStageViewVnext({ coverAssetRequired = true, onArtifactChange, readOnly, result, runId, sourceResult }: Props) {
  const parsed = useMemo(() => parseCoverArtifact(result), [result]);
  const [artifact, setArtifact] = useState<CoverArtifactVnext | null>(parsed.artifact);
  const [assets, setAssets] = useState<CoverAssetRecord[]>([]);
  const [assetState, setAssetState] = useState<'loading' | 'ready' | 'error'>('loading');
  useEffect(() => { if (parsed.artifact) setArtifact(parsed.artifact); }, [parsed.artifact]);
  useEffect(() => {
    if (!coverAssetRequired || !runId) {
      setAssets([]);
      setAssetState('ready');
      return undefined;
    }
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
  }, [coverAssetRequired, runId, sourceResult]);
  if (!artifact) return <VnextArtifactError errors={parsed.errors} label="Cover Artifact" />;
  const update = (next: CoverArtifactVnext) => { setArtifact(next); onArtifactChange(next); };
  const preview = coverAssetRequired
    ? assets.find((item) => item.asset_id === artifact.selected_asset_id) ?? assets[0]
    : undefined;
  const briefReadOnly = readOnly || coverAssetRequired && Boolean(runId) && (assetState !== 'ready' || assets.length > 0);
  return (
    <div className="vnext-artifact-workbench cover-vnext">
      <section className="vnext-cover-gallery">
        <header>
          <div><span>封面候选</span><strong>{coverAssetRequired ? (artifact.selected_asset_id ? <Check size={15} /> : <ImageOff size={15} />) : <ImageOff size={15} />}{coverAssetRequired ? (artifact.selected_asset_id ? '已选正式封面' : '待选择') : '仅保留元数据'}</strong></div>
          <span className={`vnext-cover-asset-state ${coverAssetRequired ? assetState : 'ready'}`}>
            {coverAssetRequired ? (assetState === 'loading' ? <LoaderCircle size={14} /> : assetState === 'error' ? <ShieldAlert size={14} /> : <Image size={14} />) : <ImageOff size={14} />}
            {coverAssetRequired ? (assetState === 'loading' ? '读取中' : assetState === 'error' ? '资产不可用' : `${assets.length} 张`) : '生图已跳过'}
          </span>
        </header>
        <div className={`vnext-cover-preview${preview ? '' : ' empty'}`}>
          {!coverAssetRequired ? (
            <div className="vnext-cover-preview-empty">
              <ImageOff aria-hidden="true" size={28} />
              <strong>封面生图已跳过</strong>
              <span>本次运行保留完整封面 Brief 与元数据，导出不包含图片资产。</span>
            </div>
          ) : preview ? <img alt="当前封面候选" src={coverAssetUrl(runId, preview.asset_id)} /> : (
            <div className="vnext-cover-preview-empty">
              <ImageOff aria-hidden="true" size={28} />
              <strong>{assetState === 'loading' ? '正在读取封面候选' : assetState === 'error' ? '候选资产暂不可用' : '尚未生成封面候选'}</strong>
              <span>{assetState === 'error' ? '资产存储无法访问；生成回执可在诊断中查看。' : '根据视觉 Brief 生成候选后，在此比较并选定正式封面。'}</span>
            </div>
          )}
        </div>
        {coverAssetRequired ? <div aria-label="封面候选" className="vnext-cover-candidate-rail" role="list">
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
        </div> : null}
      </section>
      <section className="vnext-artifact-section vnext-cover-brief">
        <header><div><Palette size={15} /><span>视觉 Brief</span><strong>{briefReadOnly && !readOnly ? '候选已绑定' : `${artifact.brief.palette.length} 色`}</strong></div></header>
        <label className="vnext-field"><span>核心概念</span><textarea onChange={(event) => update({ ...artifact, brief: { ...artifact.brief, concept: event.target.value } })} readOnly={briefReadOnly} rows={4} value={artifact.brief.concept} /></label>
        <label className="vnext-field"><span>画面指令</span><textarea onChange={(event) => update({ ...artifact, brief: { ...artifact.brief, image_prompt: event.target.value } })} readOnly={briefReadOnly} rows={9} value={artifact.brief.image_prompt} /></label>
        <PaletteSwatchField
          label="色彩基调"
          onChange={(palette) => update({ ...artifact, brief: { ...artifact.brief, palette } })}
          readOnly={briefReadOnly}
          values={artifact.brief.palette}
        />
        <div className="vnext-ref-field">
          <span>排除项（画面中不允许出现）</span>
          <PhraseTagField
            addLabel="新增排除项"
            ariaLabel="排除项"
            onChange={(negative_constraints) => update({ ...artifact, brief: { ...artifact.brief, negative_constraints } })}
            placeholder="例如：不要出现文字"
            readOnly={briefReadOnly}
            values={artifact.brief.negative_constraints}
          />
        </div>
      </section>
    </div>
  );
}
