import { useEffect, useMemo, useState } from "react"
import {
  ArrowDown,
  ArrowUp,
  BookCopy,
  Braces,
  CircleDot,
  Flag,
  Gauge,
  Link2,
  ShieldAlert,
  Sparkles,
  UsersRound,
} from "lucide-react"
import {
  formatCharacterCount,
  reorderVolumeContracts,
  volumeArchitectureDiagnostics,
  type VolumeArchitectureDraft,
  type VolumeContractDraft,
  type VolumeReferenceContext,
} from "../lib/phase32Volumes"
import {
  shortPhase32ArtifactRef,
  VolumeContractField,
  VolumeScopeLedger,
} from "./VolumeArchitectureEditorFields"

type Props = {
  artifact: VolumeArchitectureDraft
  artifactRef: string
  editable: boolean
  onChange: (value: Record<string, unknown>) => void
  referenceContext: VolumeReferenceContext
  revisionLabel: string
}

export function VolumeArchitectureArtifactEditor({
  artifact,
  artifactRef,
  editable,
  onChange,
  referenceContext,
  revisionLabel,
}: Props) {
  const [selectedVolumeRef, setSelectedVolumeRef] = useState(
    artifact.volumes[0]?.volume_ref ?? "",
  )
  const diagnostics = useMemo(
    () => volumeArchitectureDiagnostics(artifact),
    [artifact],
  )
  const selectedIndex = Math.max(
    0,
    artifact.volumes.findIndex(
      (volume) => volume.volume_ref === selectedVolumeRef,
    ),
  )
  const selectedVolume = artifact.volumes[selectedIndex]

  useEffect(() => {
    if (
      artifact.volumes.some((volume) => volume.volume_ref === selectedVolumeRef)
    )
      return
    setSelectedVolumeRef(artifact.volumes[0]?.volume_ref ?? "")
  }, [artifact.volumes, selectedVolumeRef])

  const patch = (volumes: VolumeContractDraft[]) => onChange({ volumes })
  const patchVolume = (value: Partial<VolumeContractDraft>) => {
    patch(
      artifact.volumes.map((volume, index) =>
        index === selectedIndex ? { ...volume, ...value } : volume,
      ),
    )
  }
  const moveVolume = (offset: -1 | 1) => {
    patch(reorderVolumeContracts(artifact.volumes, selectedIndex, offset))
  }

  return (
    <div
      className={`phase32-volumes-workbench artifact-mode-surface ${
        editable ? "is-editing" : "is-viewing"
      }`}
    >
      <nav className="phase32-volumes-rail" aria-label="卷册导航">
        <header>
          <div>
            <BookCopy size={13} />
            <span>卷册序列</span>
          </div>
          <strong>{artifact.volumes.length}</strong>
        </header>
        <div className="phase32-volumes-rail-list">
          {artifact.volumes.map((volume, index) => (
            <button
              aria-current={
                selectedVolumeRef === volume.volume_ref ? "step" : undefined
              }
              className={
                selectedVolumeRef === volume.volume_ref ? "is-active" : ""
              }
              key={volume.volume_ref}
              onClick={() => setSelectedVolumeRef(volume.volume_ref)}
              type="button"
            >
              <span>{String(index + 1).padStart(2, "0")}</span>
              <span>
                <strong>VOLUME {String(index + 1).padStart(2, "0")}</strong>
                <small>{volume.promise}</small>
                <i>
                  {referenceContext.parts[volume.part_ref]?.label ??
                    volume.part_ref}
                  <b>{formatCharacterCount(volume.length_hint)} 字</b>
                </i>
              </span>
              <em aria-hidden="true" />
            </button>
          ))}
        </div>
        <footer>
          <Link2 size={12} />
          <span>卷册标识、Part 与人物范围随候选冻结</span>
        </footer>
      </nav>

      <div className="phase32-volumes-scroll">
        <div className="phase32-volumes-mobile-nav" aria-label="卷册快捷导航">
          {artifact.volumes.map((volume, index) => (
            <button
              className={
                selectedVolumeRef === volume.volume_ref ? "is-active" : ""
              }
              key={volume.volume_ref}
              onClick={() => setSelectedVolumeRef(volume.volume_ref)}
              type="button"
            >
              V{String(index + 1).padStart(2, "0")}
            </button>
          ))}
        </div>

        <main className="phase32-volumes-canvas">
          <header className="phase32-volumes-heading">
            <div>
              <span>LONG NOVEL · VOLUME ARCHITECTURE</span>
              <h1>卷册承诺与收束合同</h1>
            </div>
            <p>每一卷都要推进全书承诺，并把可执行的进入状态交给滚动细纲。</p>
          </header>

          {selectedVolume ? (
            <section className="phase32-volume-sheet">
              <header className="phase32-volume-sheet-header">
                <div>
                  <span>{String(selectedIndex + 1).padStart(2, "0")}</span>
                  <div>
                    <strong>卷册契约</strong>
                    <code>{selectedVolume.volume_ref}</code>
                  </div>
                </div>
                <div className="phase32-volume-sheet-controls">
                  {editable ? (
                    <label>
                      <Gauge size={12} />
                      <span>软篇幅</span>
                      <input
                        aria-label="卷册软篇幅"
                        max={300_000}
                        min={2_000}
                        step={1_000}
                        type="number"
                        value={selectedVolume.length_hint}
                        onChange={(event) =>
                          patchVolume({
                            length_hint: Number(event.target.value),
                          })
                        }
                      />
                      <i>字</i>
                    </label>
                  ) : (
                    <div className="phase32-volume-length-readout">
                      <Gauge size={12} />
                      <span>软篇幅</span>
                      <strong>
                        {formatCharacterCount(selectedVolume.length_hint)} 字
                      </strong>
                    </div>
                  )}
                  {editable ? (
                    <div aria-label="调整卷册顺序">
                      <button
                        aria-label={`上移 Volume ${selectedIndex + 1}`}
                        disabled={selectedIndex === 0}
                        onClick={() => moveVolume(-1)}
                        title="上移"
                        type="button"
                      >
                        <ArrowUp size={13} />
                      </button>
                      <button
                        aria-label={`下移 Volume ${selectedIndex + 1}`}
                        disabled={selectedIndex === artifact.volumes.length - 1}
                        onClick={() => moveVolume(1)}
                        title="下移"
                        type="button"
                      >
                        <ArrowDown size={13} />
                      </button>
                    </div>
                  ) : null}
                </div>
              </header>

              <div className="phase32-volume-scope">
                <VolumeScopeLedger
                  icon={<Braces size={12} />}
                  label="Part 归属"
                >
                  <code title={selectedVolume.part_ref}>
                    {referenceContext.parts[selectedVolume.part_ref]?.label ??
                      selectedVolume.part_ref}
                  </code>
                </VolumeScopeLedger>
                <VolumeScopeLedger
                  icon={<UsersRound size={12} />}
                  label="人物范围"
                >
                  {selectedVolume.cast_subject_refs.map((ref) => (
                    <code key={ref} title={ref}>
                      {referenceContext.cast[ref]?.label ?? ref}
                    </code>
                  ))}
                </VolumeScopeLedger>
              </div>

              <div className="phase32-volume-flow" aria-hidden="true">
                <span>
                  <CircleDot size={11} /> 承诺
                </span>
                <i />
                <span>
                  <ShieldAlert size={11} /> 对抗
                </span>
                <i />
                <span>
                  <Sparkles size={11} /> 高潮
                </span>
                <i />
                <span>
                  <Flag size={11} /> 闭合
                </span>
              </div>

              <div className="phase32-volume-fields">
                <VolumeContractField
                  collaborationPath={`volumes.${selectedIndex}.promise`}
                  collaborationUnit={selectedVolume.volume_ref}
                  editable={editable}
                  icon={<CircleDot size={13} />}
                  label="本卷向读者承诺什么"
                  value={selectedVolume.promise}
                  onChange={(promise) => patchVolume({ promise })}
                />
                <VolumeContractField
                  collaborationPath={`volumes.${selectedIndex}.conflict`}
                  collaborationUnit={selectedVolume.volume_ref}
                  editable={editable}
                  icon={<ShieldAlert size={13} />}
                  label="主要冲突如何持续施压"
                  value={selectedVolume.conflict}
                  onChange={(conflict) => patchVolume({ conflict })}
                />
                <VolumeContractField
                  collaborationPath={`volumes.${selectedIndex}.climax`}
                  collaborationUnit={selectedVolume.volume_ref}
                  editable={editable}
                  icon={<Sparkles size={13} />}
                  label="高潮必须完成的不可逆变化"
                  value={selectedVolume.climax}
                  onChange={(climax) => patchVolume({ climax })}
                />
                <VolumeContractField
                  collaborationPath={`volumes.${selectedIndex}.closure`}
                  collaborationUnit={selectedVolume.volume_ref}
                  editable={editable}
                  icon={<Flag size={13} />}
                  label="本卷闭合并带往下游的状态"
                  value={selectedVolume.closure}
                  onChange={(closure) => patchVolume({ closure })}
                />
              </div>
            </section>
          ) : null}
        </main>
      </div>

      <aside className="phase32-volumes-inspector" aria-label="卷册检查器">
        <section className="phase32-volumes-inspector-stats">
          <div>
            <strong>{diagnostics.volumeCount}</strong>
            <span>卷</span>
          </div>
          <div>
            <strong>{formatCharacterCount(diagnostics.totalLengthHint)}</strong>
            <span>计划字数</span>
          </div>
          <div>
            <strong>{diagnostics.uniqueCastCount}</strong>
            <span>人物</span>
          </div>
        </section>
        <section>
          <span>Part 覆盖</span>
          <div className="phase32-volumes-coverage">
            {diagnostics.partCoverage.map((item) => (
              <div key={item.partRef}>
                <strong>
                  {referenceContext.parts[item.partRef]?.label ?? item.partRef}
                </strong>
                <small>
                  {item.volumeRefs.length} 卷 ·{" "}
                  {formatCharacterCount(item.lengthHint)} 字
                </small>
              </div>
            ))}
          </div>
        </section>
        <section>
          <span>编辑边界</span>
          <p>可编辑文学字段、软篇幅并重排现有卷册。</p>
          <small>卷册标识、Part 归属与人物范围保持冻结。</small>
        </section>
        <section>
          <span>下游交接</span>
          <p>滚动细纲按卷册契约创建有界章节 Window。</p>
          <small>章节、场景与 handoff 不在本页提前编辑。</small>
        </section>
        <section>
          <span>版本来源</span>
          <code title={artifactRef}>
            {shortPhase32ArtifactRef(artifactRef)}
          </code>
          <small>{revisionLabel}</small>
          <small>
            {editable ? "全部卷册随当前草稿一次保存。" : "当前为稳定阅读视图。"}
          </small>
        </section>
      </aside>
    </div>
  )
}
