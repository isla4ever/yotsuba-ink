import {
  Check,
  FileImage,
  Image as ImageIcon,
  Layers3,
  LockKeyhole,
  Palette,
  ScanLine,
  ShieldCheck,
} from "lucide-react"
import type { CoverAssetRecord } from "../contracts/coverAsset"
import {
  formatCoverBytes,
  selectedPhase32CoverAsset,
  type Phase32CoverArtifact,
} from "../lib/phase32Cover"
import { coverAssetContentUrl } from "../services/coverAssetApi"

type Props = {
  artifact: Phase32CoverArtifact
  artifactRef: string
  assets: CoverAssetRecord[]
  canSelect: boolean
  generationAttempt: number
  projectTitle: string
  revisionLabel: string
  runId: string
  onSelect: (assetRef: string) => void
}

export function Phase32CoverWorkbench({
  artifact,
  artifactRef,
  assets,
  canSelect,
  generationAttempt,
  projectTitle,
  revisionLabel,
  runId,
  onSelect,
}: Props) {
  const assetByRef = new Map(assets.map((asset) => [asset.asset_id, asset]))
  const imageDeferred = artifact.image_acceptance_status === "image_deferred"
  const selectedAsset = selectedPhase32CoverAsset(artifact, assets)
  const firstCandidate = artifact.candidates[0]
  const previewAsset =
    selectedAsset ??
    (firstCandidate ? assetByRef.get(firstCandidate.asset_ref) : null) ??
    null
  const previewCandidate = artifact.candidates.find(
    (candidate) => candidate.asset_ref === previewAsset?.asset_id,
  )

  return (
    <div className="phase32-cover-workbench">
      <nav className="phase32-cover-rail" aria-label="封面候选资产">
        <header>
          <div>
            <Layers3 size={13} />
            <span>候选资产</span>
          </div>
          <strong>{artifact.candidates.length}</strong>
        </header>
        <div className="phase32-cover-candidate-list">
          {artifact.candidates.length === 0 ? (
            <div className="px-3 py-4 text-xs text-fog">
              图片验收暂缓；当前仅保存 CoverBrief，不生成或选择图片资产。
            </div>
          ) : (
            artifact.candidates.map((candidate, index) => {
              const asset = assetByRef.get(candidate.asset_ref)
              const selected =
                candidate.asset_ref === artifact.selected_asset_ref
              return (
                <button
                  aria-current={selected ? "true" : undefined}
                  aria-label={`选择封面候选 ${index + 1}：${candidate.alt_text}`}
                  className={selected ? "is-active" : ""}
                  disabled={!canSelect || !asset}
                  key={candidate.asset_ref}
                  onClick={() => onSelect(candidate.asset_ref)}
                  type="button"
                >
                  <span className="phase32-cover-thumb">
                    {asset ? (
                      <img alt="" src={coverAssetContentUrl(runId, asset)} />
                    ) : (
                      <FileImage size={15} />
                    )}
                  </span>
                  <span>
                    <strong>方向 {String(index + 1).padStart(2, "0")}</strong>
                    <small>
                      {asset
                        ? `${asset.width} × ${asset.height}`
                        : "资产核验中"}
                    </small>
                    <i>{selected ? "正式选择" : "点击审阅"}</i>
                  </span>
                  <em>{selected ? <Check size={9} /> : null}</em>
                </button>
              )
            })
          )}
        </div>
        <footer>
          <LockKeyhole size={12} />
          <span>选择写入当前草稿；定稿后资产与正文交付永久绑定</span>
        </footer>
      </nav>

      <main className="phase32-cover-canvas">
        <div className="phase32-cover-canvas-inner">
          <header className="phase32-cover-heading">
            <div>
              <span>COVER DIRECTION · GENERATION {generationAttempt || 1}</span>
              <h1>{projectTitle || "待定标题"}</h1>
            </div>
            <div>
              <small>{revisionLabel}</small>
              <strong>
                {selectedAsset ? "正式封面待定稿" : "正在审阅候选"}
              </strong>
            </div>
          </header>

          <section className="phase32-cover-preview" aria-label="封面大图预览">
            <div className="phase32-cover-preview-frame">
              {previewAsset ? (
                <img
                  alt={previewCandidate?.alt_text || "封面候选预览"}
                  src={coverAssetContentUrl(runId, previewAsset)}
                />
              ) : (
                <div className="phase32-cover-preview-missing">
                  <ImageIcon size={24} />
                  <span>真实封面资产尚未就绪</span>
                </div>
              )}
              <span className="phase32-cover-safe-line" aria-hidden="true" />
              <div className="phase32-cover-preview-state">
                {selectedAsset ? (
                  <ShieldCheck size={12} />
                ) : (
                  <ScanLine size={12} />
                )}
                <span>
                  {imageDeferred
                    ? "IMAGE ACCEPTANCE DEFERRED"
                    : selectedAsset
                      ? "SELECTED AS FINAL"
                      : "PREVIEW ONLY"}
                </span>
              </div>
            </div>
            <div className="phase32-cover-preview-copy">
              <span>
                {previewCandidate?.alt_text ||
                  (imageDeferred ? "CoverBrief 视觉方向" : "等待资产")}
              </span>
              <p>{previewCandidate?.visual_notes || artifact.brief.concept}</p>
            </div>
          </section>
        </div>
      </main>

      <aside
        className="phase32-cover-inspector"
        aria-label="封面视觉与资产回执"
      >
        <header>
          <Palette size={13} />
          <div>
            <span>视觉检查器</span>
            <small>Brief / Prompt / Receipt</small>
          </div>
        </header>

        <section>
          <span>视觉命题</span>
          <p>{artifact.brief.concept}</p>
        </section>

        <section>
          <span>色板</span>
          <div className="phase32-cover-palette">
            {artifact.brief.palette.map((tone, index) => (
              <div key={`${tone}-${index}`}>
                <i className={`tone-${(index % 6) + 1}`} aria-hidden="true" />
                <small>{tone}</small>
              </div>
            ))}
          </div>
        </section>

        <section>
          <span>图片 Prompt</span>
          <p className="is-prompt">{artifact.brief.image_prompt}</p>
        </section>

        {artifact.brief.negative_constraints.length ? (
          <section>
            <span>排除项</span>
            <ul>
              {artifact.brief.negative_constraints.map((item) => (
                <li key={item}>{item}</li>
              ))}
            </ul>
          </section>
        ) : null}

        <section className="phase32-cover-receipt">
          <span>当前资产回执</span>
          <dl>
            <div>
              <dt>尺寸</dt>
              <dd>
                {previewAsset
                  ? `${previewAsset.width} × ${previewAsset.height}`
                  : imageDeferred
                    ? "图片验收暂缓"
                    : "-"}
              </dd>
            </div>
            <div>
              <dt>文件</dt>
              <dd>
                {previewAsset ? formatCoverBytes(previewAsset.size_bytes) : "-"}
              </dd>
            </div>
            <div>
              <dt>SHA-256</dt>
              <dd>{previewAsset ? shortDigest(previewAsset.sha256) : "-"}</dd>
            </div>
            <div>
              <dt>Artifact</dt>
              <dd>{shortRef(artifactRef)}</dd>
            </div>
          </dl>
        </section>
      </aside>
    </div>
  )
}

function shortDigest(value: string) {
  return value ? `${value.slice(0, 8)}…${value.slice(-6)}` : "-"
}

function shortRef(value: string) {
  return value.length > 24 ? `${value.slice(0, 14)}…${value.slice(-7)}` : value
}
