import {
  AlertTriangle,
  Check,
  CheckCircle2,
  ImageOff,
  RefreshCw,
} from "lucide-react"
import type { FrozenCoverAssetBinding } from "../contracts/run"
import { coverAssetContentUrl } from "../services/coverAssetApi"
import type { useCoverAssets } from "../state/useCoverAssets"
import type { CoverArtifact } from "../contracts/delivery"

export function CoverAssetGallery({
  artifact,
  assetState,
  binding,
  editable,
  includeCoverImage,
  onSelect,
  runId,
}: {
  artifact: CoverArtifact
  assetState: ReturnType<typeof useCoverAssets>
  binding: FrozenCoverAssetBinding | undefined
  editable: boolean
  includeCoverImage: boolean
  onSelect: (assetId: string) => void
  runId: string
}) {
  const selectedAsset = assetState.assets.find(
    (item) => item.asset_id === artifact.selected_asset_id,
  )
  return (
    <section className="min-w-0">
      <div className="flex items-center justify-between gap-3 mb-3">
        <div>
          <span className="text-xs font-medium text-ink">不可变候选资产</span>
          <p className="text-[10px] text-fog mt-0.5">
            {includeCoverImage
              ? `第 ${assetState.generationAttempt || "—"} 次生成 · ${assetState.assets.length} 张`
              : "本次 Run 的冻结导出配置不包含封面图片"}
          </p>
        </div>
        {assetState.status === "loading" && (
          <span className="text-xs text-action flex items-center gap-1.5">
            <RefreshCw size={12} className="animate-spin" /> 读取中
          </span>
        )}
      </div>

      {!includeCoverImage ? (
        <NoImageDelivery binding={binding} />
      ) : assetState.status === "ready" && assetState.assets.length ? (
        <div
          className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-3 gap-3"
          role="list"
          aria-label="封面候选"
        >
          {assetState.assets.map((asset) => {
            const selected = artifact.selected_asset_id === asset.asset_id
            return (
              <button
                type="button"
                role="listitem"
                aria-pressed={selected}
                key={asset.asset_id}
                disabled={!editable}
                onClick={() => onSelect(asset.asset_id)}
                className={`group text-left overflow-hidden rounded-lg border-2 bg-surface transition-colors ${
                  selected
                    ? "border-action"
                    : "border-hairline hover:border-ash"
                } disabled:cursor-default`}
              >
                <div className="relative aspect-[2/3] bg-base overflow-hidden">
                  <img
                    src={coverAssetContentUrl(runId, asset)}
                    alt={`封面候选 ${asset.candidate_index}`}
                    className="w-full h-full object-cover transition-opacity group-hover:opacity-95"
                  />
                  <span className="absolute top-2 left-2 bg-black/65 text-white text-[10px] font-mono rounded px-1.5 py-0.5">
                    {String(asset.candidate_index).padStart(2, "0")}
                  </span>
                  {selected && (
                    <span className="absolute top-2 right-2 w-6 h-6 grid place-items-center rounded-full bg-action text-white">
                      <Check size={13} />
                    </span>
                  )}
                </div>
                <div className="p-3">
                  <div className="flex items-center justify-between gap-2">
                    <strong className="text-xs text-ink">
                      候选 {String(asset.candidate_index).padStart(2, "0")}
                    </strong>
                    <span className="text-[10px] font-mono text-fog">
                      {asset.width}×{asset.height}
                    </span>
                  </div>
                  <p className="text-[10px] text-fog mt-1 truncate">
                    {selected ? "已选为正式封面" : asset.asset_id}
                  </p>
                </div>
              </button>
            )
          })}
        </div>
      ) : (
        <AssetEmpty state={assetState} />
      )}

      {selectedAsset && (
        <div className="mt-3 banner-success">
          <CheckCircle2 size={13} />
          <span>
            已选择候选 {selectedAsset.candidate_index} · {selectedAsset.asset_id}
          </span>
        </div>
      )}
    </section>
  )
}

function NoImageDelivery({
  binding,
}: {
  binding: FrozenCoverAssetBinding | undefined
}) {
  return (
    <div className="min-h-[420px] border border-hairline bg-surface rounded-lg grid place-items-center px-6 text-center">
      <div className="max-w-sm">
        <ImageOff size={30} className="text-fog mx-auto mb-4" />
        <h2 className="text-sm font-semibold text-ink">本次不生成封面图片</h2>
        <p className="text-xs text-fog leading-6 mt-2">
          视觉 Brief 会作为正式 Artifact 保留；Export 将按冻结配置交付不含图片的作品包。
        </p>
        <div className="mt-5 grid grid-cols-2 gap-2 text-left">
          <BindingFact label="图片模型" value={binding?.model || "未绑定"} />
          <BindingFact label="目标尺寸" value={binding?.size || "—"} />
        </div>
      </div>
    </div>
  )
}

function AssetEmpty({
  state,
}: {
  state: ReturnType<typeof useCoverAssets>
}) {
  return (
    <div className="min-h-[420px] border border-hairline bg-surface rounded-lg grid place-items-center px-6 text-center">
      <div className="max-w-sm">
        {state.status === "error" ? (
          <AlertTriangle size={28} className="text-risk mx-auto mb-4" />
        ) : (
          <ImageOff size={28} className="text-fog mx-auto mb-4" />
        )}
        <h2 className="text-sm font-semibold text-ink">
          {state.status === "loading"
            ? "正在读取封面候选"
            : state.status === "error"
              ? "封面资产暂不可用"
              : "尚未生成封面候选"}
        </h2>
        <p className="text-xs text-fog leading-6 mt-2">
          {state.status === "error"
            ? state.error
            : "图片 Provider 完成生成并写入不可变资产后，候选会出现在这里。"}
        </p>
      </div>
    </div>
  )
}

function BindingFact({ label, value }: { label: string; value: string }) {
  return (
    <div className="border border-ghost rounded p-3 bg-base">
      <span className="text-[10px] text-fog block">{label}</span>
      <strong className="text-xs text-ink font-mono block mt-1 truncate">
        {value}
      </strong>
    </div>
  )
}
