import { useEffect, useMemo, useState, type ReactNode } from "react"
import {
  ArrowDown,
  ArrowRight,
  ArrowUp,
  BadgeCheck,
  Clapperboard,
  Clock3,
  Crosshair,
  Eye,
  Flag,
  Link2,
  ListOrdered,
  Sparkles,
  UsersRound,
} from "lucide-react"
import {
  beatBoardDiagnostics,
  reorderBeatBoardBeats,
  shortBeatRef,
  type BeatBoardBeatDraft,
  type BeatBoardDraft,
  type BeatBoardReferenceContext,
} from "../lib/phase32BeatBoard"
import {
  BeatBoardIconButton,
  BeatBoardReadableField,
  BeatBoardReferenceEditor,
  BeatBoardTextField,
} from "./BeatBoardEditorFields"

type Props = {
  artifact: BeatBoardDraft
  artifactRef: string
  editable: boolean
  onChange: (value: Record<string, unknown>) => void
  referenceContext: BeatBoardReferenceContext
  revisionLabel: string
}

type BeatBoardSection = "chain" | "intent"

type ChainFieldProps = {
  collaborationPath: string
  collaborationUnit: string
  editable: boolean
  emphasized?: boolean
  icon: ReactNode
  label: string
  onChange: (value: string) => void
  step: string
  value: string
}

export function BeatBoardArtifactEditor({
  artifact,
  artifactRef,
  editable,
  onChange,
  referenceContext,
  revisionLabel,
}: Props) {
  const [selectedBeatRef, setSelectedBeatRef] = useState(
    artifact.beats[0]?.beat_ref ?? "",
  )
  const [section, setSection] = useState<BeatBoardSection>("chain")
  const diagnostics = useMemo(() => beatBoardDiagnostics(artifact), [artifact])
  const selectedIndex = Math.max(
    0,
    artifact.beats.findIndex((beat) => beat.beat_ref === selectedBeatRef),
  )
  const selectedBeat = artifact.beats[selectedIndex]
  const previousBeat = artifact.beats[selectedIndex - 1]
  const nextBeat = artifact.beats[selectedIndex + 1]

  useEffect(() => {
    if (artifact.beats.some((beat) => beat.beat_ref === selectedBeatRef)) return
    setSelectedBeatRef(artifact.beats[0]?.beat_ref ?? "")
  }, [artifact.beats, selectedBeatRef])

  useEffect(() => setSection("chain"), [selectedBeatRef])

  const patch = (beats: BeatBoardBeatDraft[]) => onChange({ beats })
  const patchBeat = (value: Partial<BeatBoardBeatDraft>) => {
    patch(
      artifact.beats.map((beat, index) =>
        index === selectedIndex ? { ...beat, ...value } : beat,
      ),
    )
  }
  const moveBeat = (offset: -1 | 1) => {
    patch(reorderBeatBoardBeats(artifact.beats, selectedIndex, offset))
  }

  return (
    <div
      className={`beat-board-workbench artifact-mode-surface ${
        editable ? "is-editing" : "is-viewing"
      }`}
    >
      <nav className="beat-board-rail" aria-label="因果节拍导航">
        <header>
          <div>
            <ListOrdered size={13} />
            <span>因果节拍</span>
          </div>
          <strong>{artifact.beats.length}</strong>
        </header>
        <div className="beat-board-rail-list">
          {artifact.beats.map((beat, index) => (
            <button
              aria-current={
                selectedBeatRef === beat.beat_ref ? "step" : undefined
              }
              className={selectedBeatRef === beat.beat_ref ? "is-active" : ""}
              key={beat.beat_ref}
              onClick={() => setSelectedBeatRef(beat.beat_ref)}
              type="button"
            >
              <span>{String(index + 1).padStart(2, "0")}</span>
              <span>
                <strong>{beat.dramatic_job}</strong>
                <small>{beat.character_decision}</small>
                <i>
                  <Clock3 size={9} /> {beat.timing_hint}
                </i>
              </span>
              <em aria-hidden="true" />
            </button>
          ))}
        </div>
        <footer>
          <Link2 size={12} />
          <span>Beat 身份已冻结；顺序决定 Scene Deck 的规划上下文</span>
        </footer>
      </nav>

      <div className="beat-board-scroll">
        <div className="beat-board-mobile-nav" aria-label="因果节拍快捷导航">
          {artifact.beats.map((beat, index) => (
            <button
              className={selectedBeatRef === beat.beat_ref ? "is-active" : ""}
              key={beat.beat_ref}
              onClick={() => setSelectedBeatRef(beat.beat_ref)}
              type="button"
            >
              {String(index + 1).padStart(2, "0")}
            </button>
          ))}
        </div>

        <main className="beat-board-canvas">
          <header className="beat-board-heading">
            <div>
              <span>SCREENPLAY SAMPLE · BEAT BOARD</span>
              <h1>屏幕决策节拍</h1>
            </div>
            <p>只保留能被看见的压力、决定和结果，为场景规划建立清晰骨架。</p>
          </header>

          {selectedBeat ? (
            <section className="beat-board-sheet">
              <header className="beat-board-sheet-header">
                <div className="beat-board-identity">
                  <span>{String(selectedIndex + 1).padStart(2, "0")}</span>
                  <div>
                    <small>当前节拍</small>
                    <strong>{shortBeatRef(selectedBeat.beat_ref)}</strong>
                    <code>{selectedBeat.beat_ref}</code>
                  </div>
                </div>
                <div className="beat-board-sheet-controls">
                  {editable ? (
                    <label className="beat-board-timing-editor">
                      <Clock3 size={12} />
                      <span>节奏提示</span>
                      <input
                        aria-label="节奏提示"
                        onChange={(event) =>
                          patchBeat({ timing_hint: event.target.value })
                        }
                        value={selectedBeat.timing_hint}
                      />
                    </label>
                  ) : (
                    <div className="beat-board-timing-readout">
                      <Clock3 size={12} />
                      <span>节奏提示</span>
                      <strong>{selectedBeat.timing_hint}</strong>
                    </div>
                  )}
                  {editable ? (
                    <div aria-label="调整 Beat 顺序">
                      <BeatBoardIconButton
                        disabled={selectedIndex === 0}
                        label={`上移节拍 ${selectedIndex + 1}`}
                        onClick={() => moveBeat(-1)}
                      >
                        <ArrowUp size={13} />
                      </BeatBoardIconButton>
                      <BeatBoardIconButton
                        disabled={selectedIndex === artifact.beats.length - 1}
                        label={`下移节拍 ${selectedIndex + 1}`}
                        onClick={() => moveBeat(1)}
                      >
                        <ArrowDown size={13} />
                      </BeatBoardIconButton>
                    </div>
                  ) : null}
                </div>
              </header>

              <div className="artifact-section-tabs" role="tablist">
                <button
                  aria-selected={section === "chain"}
                  className={section === "chain" ? "is-active" : ""}
                  onClick={() => setSection("chain")}
                  role="tab"
                  type="button"
                >
                  <Crosshair size={12} /> 决策链 <span>01</span>
                </button>
                <button
                  aria-selected={section === "intent"}
                  className={section === "intent" ? "is-active" : ""}
                  onClick={() => setSection("intent")}
                  role="tab"
                  type="button"
                >
                  <Flag size={12} /> 任务与铺垫 <span>02</span>
                </button>
              </div>

              {section === "chain" ? (
                <div className="beat-board-chain" role="tabpanel">
                  <div className="beat-board-chain-grid">
                    <ChainField
                      collaborationPath={`beats.${selectedIndex}.visible_pressure`}
                      collaborationUnit={selectedBeat.beat_ref}
                      editable={editable}
                      icon={<Eye size={12} />}
                      label="可见压力"
                      onChange={(visible_pressure) =>
                        patchBeat({ visible_pressure })
                      }
                      step="01"
                      value={selectedBeat.visible_pressure}
                    />
                    <ArrowRight aria-hidden="true" size={17} />
                    <ChainField
                      collaborationPath={`beats.${selectedIndex}.character_decision`}
                      collaborationUnit={selectedBeat.beat_ref}
                      editable={editable}
                      emphasized
                      icon={<Crosshair size={12} />}
                      label="台面决定"
                      onChange={(character_decision) =>
                        patchBeat({ character_decision })
                      }
                      step="02"
                      value={selectedBeat.character_decision}
                    />
                    <ArrowRight aria-hidden="true" size={17} />
                    <ChainField
                      collaborationPath={`beats.${selectedIndex}.outcome`}
                      collaborationUnit={selectedBeat.beat_ref}
                      editable={editable}
                      icon={<Sparkles size={12} />}
                      label="新局面"
                      onChange={(outcome) => patchBeat({ outcome })}
                      step="03"
                      value={selectedBeat.outcome}
                    />
                  </div>
                  <div className="beat-board-continuity">
                    <div>
                      <span>上一拍结果</span>
                      <p>
                        {previousBeat?.outcome ?? "样片从此处进入第一重压力。"}
                      </p>
                    </div>
                    <ArrowRight aria-hidden="true" size={14} />
                    <div className="is-current">
                      <span>当前拍决定</span>
                      <p>{selectedBeat.character_decision}</p>
                    </div>
                    <ArrowRight aria-hidden="true" size={14} />
                    <div>
                      <span>下一拍压力</span>
                      <p>
                        {nextBeat?.visible_pressure ??
                          "当前结果进入 Scene Deck 收束。"}
                      </p>
                    </div>
                  </div>
                </div>
              ) : (
                <div className="beat-board-intent" role="tabpanel">
                  <div className="beat-board-dramatic-job">
                    {editable ? (
                      <BeatBoardTextField
                        collaborationPath={`beats.${selectedIndex}.dramatic_job`}
                        collaborationUnit={selectedBeat.beat_ref}
                        emphasized
                        icon={<Clapperboard size={12} />}
                        label="本拍戏剧任务"
                        onChange={(dramatic_job) => patchBeat({ dramatic_job })}
                        value={selectedBeat.dramatic_job}
                      />
                    ) : (
                      <BeatBoardReadableField
                        emphasized
                        icon={<Clapperboard size={12} />}
                        label="本拍戏剧任务"
                        value={selectedBeat.dramatic_job}
                      />
                    )}
                  </div>
                  <div className="beat-board-reference-zone">
                    <header>
                      <div>
                        <Link2 size={12} />
                        <span>铺垫与回收</span>
                      </div>
                      <small>
                        {selectedBeat.setup_or_payoff_refs.length} 条引用
                      </small>
                    </header>
                    {editable ? (
                      <BeatBoardReferenceEditor
                        onChange={(setup_or_payoff_refs) =>
                          patchBeat({ setup_or_payoff_refs })
                        }
                        value={selectedBeat.setup_or_payoff_refs}
                      />
                    ) : (
                      <div className="beat-board-reference-list">
                        {selectedBeat.setup_or_payoff_refs.length ? (
                          selectedBeat.setup_or_payoff_refs.map((reference) => (
                            <code key={reference}>{reference}</code>
                          ))
                        ) : (
                          <em>本拍尚未绑定 setup / payoff 引用</em>
                        )}
                      </div>
                    )}
                  </div>
                  <div className="beat-board-brief-alignment">
                    <div>
                      <span>样片可见冲突</span>
                      <p>
                        {referenceContext.brief.visibleConflict ||
                          "未读取到 Brief 可见冲突"}
                      </p>
                    </div>
                    <div>
                      <span>结尾效果</span>
                      <p>
                        {referenceContext.brief.endingEffect ||
                          "未读取到 Brief 结尾效果"}
                      </p>
                    </div>
                  </div>
                </div>
              )}
            </section>
          ) : null}
        </main>
      </div>

      <aside className="beat-board-inspector" aria-label="Beat Board 检查器">
        <section>
          <span>结构检查</span>
          <dl>
            <div>
              <dt>Beat</dt>
              <dd>{diagnostics.beatCount}</dd>
            </div>
            <div>
              <dt>引用</dt>
              <dd>{diagnostics.uniqueReferenceCount}</dd>
            </div>
            <div>
              <dt>无引用</dt>
              <dd>{diagnostics.beatsWithoutReference.length}</dd>
            </div>
          </dl>
          <small
            className={
              diagnostics.beatsWithoutReference.length ? "is-warning" : ""
            }
          >
            {diagnostics.beatsWithoutReference.length
              ? `${diagnostics.beatsWithoutReference.length} 个 Beat 尚无 setup / payoff 覆盖`
              : "每个 Beat 均有 setup / payoff 覆盖"}
          </small>
        </section>
        <section>
          <span>样片承诺</span>
          <div className="beat-board-inspector-promise">
            <BadgeCheck size={13} />
            <strong>{referenceContext.brief.sampleType || "剧本样片"}</strong>
            <small>
              {referenceContext.brief.audiencePromise ||
                "等待读取 Brief 观众承诺"}
            </small>
            <code>
              {referenceContext.brief.targetMinutes
                ? `${referenceContext.brief.targetMinutes} MIN`
                : "SOFT TARGET"}
            </code>
          </div>
        </section>
        <section>
          <span>引用覆盖</span>
          <div className="beat-board-inspector-coverage">
            {diagnostics.referenceCoverage.length ? (
              diagnostics.referenceCoverage.map((item) => (
                <div key={item.reference}>
                  <code>{item.reference}</code>
                  <small>{item.beatRefs.length} Beat</small>
                </div>
              ))
            ) : (
              <small>当前没有 setup / payoff 引用。</small>
            )}
          </div>
        </section>
        <section>
          <span>已确认人物名册</span>
          <div className="beat-board-cast-list">
            {Object.values(referenceContext.cast).map((member) => (
              <div key={member.ref}>
                <UsersRound size={10} />
                <span>{member.label}</span>
                <small>{member.role || member.ref}</small>
              </div>
            ))}
            {Object.keys(referenceContext.cast).length === 0 ? (
              <small>等待读取 Cast</small>
            ) : null}
          </div>
        </section>
        <section>
          <span>Artifact 版本</span>
          <code>{artifactRef}</code>
          <small>{revisionLabel}</small>
        </section>
      </aside>
    </div>
  )
}

function ChainField({
  collaborationPath,
  collaborationUnit,
  editable,
  emphasized = false,
  icon,
  label,
  onChange,
  step,
  value,
}: ChainFieldProps) {
  return (
    <article className={emphasized ? "is-pivot" : ""}>
      <header>
        <span>{step}</span>
        <div>
          {icon}
          {label}
        </div>
      </header>
      {editable ? (
        <BeatBoardTextField
          collaborationPath={collaborationPath}
          collaborationUnit={collaborationUnit}
          emphasized={emphasized}
          label={label}
          onChange={onChange}
          value={value}
        />
      ) : (
        <BeatBoardReadableField
          emphasized={emphasized}
          label={label}
          value={value}
        />
      )}
    </article>
  )
}
