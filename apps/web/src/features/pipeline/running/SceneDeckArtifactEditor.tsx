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
  Film,
  MapPin,
  ShieldAlert,
  SlidersHorizontal,
  UsersRound,
} from "lucide-react"
import {
  formatPageTarget,
  reorderSceneDeckScenes,
  sceneDeckDiagnostics,
  shortSceneRef,
  type SceneDeckDraft,
  type SceneDeckReferenceContext,
  type SceneDeckSceneDraft,
} from "../lib/phase32SceneDeck"
import {
  SceneDeckCastEditor,
  SceneDeckIconButton,
  SceneDeckMetadataField,
  SceneDeckReadableField,
  SceneDeckTextField,
} from "./SceneDeckEditorFields"

type Props = {
  artifact: SceneDeckDraft
  artifactRef: string
  editable: boolean
  onChange: (value: Record<string, unknown>) => void
  referenceContext: SceneDeckReferenceContext
  revisionLabel: string
}

type SceneDeckSection = "blocking" | "production"

type BlockingFieldProps = {
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

export function SceneDeckArtifactEditor({
  artifact,
  artifactRef,
  editable,
  onChange,
  referenceContext,
  revisionLabel,
}: Props) {
  const [selectedSceneRef, setSelectedSceneRef] = useState(
    artifact.scenes[0]?.scene_ref ?? "",
  )
  const [section, setSection] = useState<SceneDeckSection>("blocking")
  const diagnostics = useMemo(
    () => sceneDeckDiagnostics(artifact, referenceContext),
    [artifact, referenceContext],
  )
  const selectedIndex = Math.max(
    0,
    artifact.scenes.findIndex((scene) => scene.scene_ref === selectedSceneRef),
  )
  const selectedScene = artifact.scenes[selectedIndex]
  const previousScene = artifact.scenes[selectedIndex - 1]
  const nextScene = artifact.scenes[selectedIndex + 1]

  useEffect(() => {
    if (artifact.scenes.some((scene) => scene.scene_ref === selectedSceneRef))
      return
    setSelectedSceneRef(artifact.scenes[0]?.scene_ref ?? "")
  }, [artifact.scenes, selectedSceneRef])

  useEffect(() => setSection("blocking"), [selectedSceneRef])

  const patch = (scenes: SceneDeckSceneDraft[]) => onChange({ scenes })
  const patchScene = (value: Partial<SceneDeckSceneDraft>) => {
    patch(
      artifact.scenes.map((scene, index) =>
        index === selectedIndex ? { ...scene, ...value } : scene,
      ),
    )
  }
  const moveScene = (offset: -1 | 1) => {
    patch(reorderSceneDeckScenes(artifact.scenes, selectedIndex, offset))
  }

  return (
    <div
      className={`scene-deck-workbench artifact-mode-surface ${
        editable ? "is-editing" : "is-viewing"
      }`}
    >
      <nav className="scene-deck-rail" aria-label="场景调度导航">
        <header>
          <div>
            <Film size={13} />
            <span>场景序列</span>
          </div>
          <strong>{artifact.scenes.length}</strong>
        </header>
        <div className="scene-deck-rail-list">
          {artifact.scenes.map((scene, index) => (
            <button
              aria-current={
                selectedSceneRef === scene.scene_ref ? "step" : undefined
              }
              className={
                selectedSceneRef === scene.scene_ref ? "is-active" : ""
              }
              key={scene.scene_ref}
              onClick={() => setSelectedSceneRef(scene.scene_ref)}
              type="button"
            >
              <span>{String(index + 1).padStart(2, "0")}</span>
              <span>
                <strong>{scene.heading}</strong>
                <small>{scene.location_and_time}</small>
                <i>
                  <UsersRound size={9} /> {scene.cast_subject_refs.length} 人
                  <b>{formatPageTarget(scene.soft_page_target)} 页</b>
                </i>
              </span>
              <em aria-hidden="true" />
            </button>
          ))}
        </div>
        <footer>
          <Clapperboard size={12} />
          <span>Scene 身份已冻结；顺序决定 Script 的场次交接</span>
        </footer>
      </nav>

      <div className="scene-deck-scroll">
        <div className="scene-deck-mobile-nav" aria-label="场景快捷导航">
          {artifact.scenes.map((scene, index) => (
            <button
              className={
                selectedSceneRef === scene.scene_ref ? "is-active" : ""
              }
              key={scene.scene_ref}
              onClick={() => setSelectedSceneRef(scene.scene_ref)}
              type="button"
            >
              S{String(index + 1).padStart(2, "0")}
            </button>
          ))}
        </div>

        <main className="scene-deck-canvas">
          <header className="scene-deck-heading">
            <div>
              <span>SCREENPLAY SAMPLE · SCENE DECK</span>
              <h1>场景调度台</h1>
            </div>
            <p>
              把已确认节拍变成可拍摄的行动、对抗与结果，不写小说式内心梗概。
            </p>
          </header>

          {selectedScene ? (
            <section className="scene-deck-sheet">
              <header className="scene-deck-sheet-header">
                <div className="scene-deck-identity">
                  <span>{String(selectedIndex + 1).padStart(2, "0")}</span>
                  <div>
                    <small>当前场次</small>
                    <strong>{shortSceneRef(selectedScene.scene_ref)}</strong>
                    <code>{selectedScene.scene_ref}</code>
                  </div>
                </div>
                <div className="scene-deck-sheet-controls">
                  {editable ? (
                    <label className="scene-deck-page-editor">
                      <Clock3 size={12} />
                      <span>软页数</span>
                      <input
                        aria-label="软页数"
                        max="50"
                        min="0.5"
                        onChange={(event) =>
                          patchScene({
                            soft_page_target: Number(event.target.value),
                          })
                        }
                        step="0.5"
                        type="number"
                        value={selectedScene.soft_page_target}
                      />
                    </label>
                  ) : (
                    <div className="scene-deck-page-readout">
                      <Clock3 size={12} />
                      <span>软页数</span>
                      <strong>
                        {formatPageTarget(selectedScene.soft_page_target)} P
                      </strong>
                    </div>
                  )}
                  {editable ? (
                    <div aria-label="调整场景顺序">
                      <SceneDeckIconButton
                        disabled={selectedIndex === 0}
                        label={`上移场景 ${selectedIndex + 1}`}
                        onClick={() => moveScene(-1)}
                      >
                        <ArrowUp size={13} />
                      </SceneDeckIconButton>
                      <SceneDeckIconButton
                        disabled={selectedIndex === artifact.scenes.length - 1}
                        label={`下移场景 ${selectedIndex + 1}`}
                        onClick={() => moveScene(1)}
                      >
                        <ArrowDown size={13} />
                      </SceneDeckIconButton>
                    </div>
                  ) : null}
                </div>
              </header>

              <div className="artifact-section-tabs" role="tablist">
                <button
                  aria-selected={section === "blocking"}
                  className={section === "blocking" ? "is-active" : ""}
                  onClick={() => setSection("blocking")}
                  role="tab"
                  type="button"
                >
                  <Crosshair size={12} /> 场景调度 <span>01</span>
                </button>
                <button
                  aria-selected={section === "production"}
                  className={section === "production" ? "is-active" : ""}
                  onClick={() => setSection("production")}
                  role="tab"
                  type="button"
                >
                  <SlidersHorizontal size={12} /> 制作信息 <span>02</span>
                </button>
              </div>

              {section === "blocking" ? (
                <div className="scene-deck-blocking" role="tabpanel">
                  <div className="scene-deck-blocking-grid">
                    <BlockingField
                      collaborationPath={`scenes.${selectedIndex}.visible_goal`}
                      collaborationUnit={selectedScene.scene_ref}
                      editable={editable}
                      icon={<Eye size={12} />}
                      label="可见目标"
                      onChange={(visible_goal) => patchScene({ visible_goal })}
                      step="01"
                      value={selectedScene.visible_goal}
                    />
                    <ArrowRight aria-hidden="true" size={17} />
                    <BlockingField
                      collaborationPath={`scenes.${selectedIndex}.opposition`}
                      collaborationUnit={selectedScene.scene_ref}
                      editable={editable}
                      emphasized
                      icon={<ShieldAlert size={12} />}
                      label="台面对抗"
                      onChange={(opposition) => patchScene({ opposition })}
                      step="02"
                      value={selectedScene.opposition}
                    />
                    <ArrowRight aria-hidden="true" size={17} />
                    <BlockingField
                      collaborationPath={`scenes.${selectedIndex}.outcome`}
                      collaborationUnit={selectedScene.scene_ref}
                      editable={editable}
                      icon={<BadgeCheck size={12} />}
                      label="场景结果"
                      onChange={(outcome) => patchScene({ outcome })}
                      step="03"
                      value={selectedScene.outcome}
                    />
                  </div>
                  <div className="scene-deck-continuity">
                    <div>
                      <span>上一场结果</span>
                      <p>
                        {previousScene?.outcome ?? "样片从本场进入可见行动。"}
                      </p>
                    </div>
                    <ArrowRight aria-hidden="true" size={14} />
                    <div className="is-current">
                      <span>当前场目标</span>
                      <p>{selectedScene.visible_goal}</p>
                    </div>
                    <ArrowRight aria-hidden="true" size={14} />
                    <div>
                      <span>下一场入口</span>
                      <p>
                        {nextScene?.visible_goal ??
                          "当前结果作为 Script 收束场次的入口。"}
                      </p>
                    </div>
                  </div>
                </div>
              ) : (
                <div className="scene-deck-production" role="tabpanel">
                  <div className="scene-deck-metadata-grid">
                    {editable ? (
                      <>
                        <SceneDeckMetadataField
                          collaborationPath={`scenes.${selectedIndex}.heading`}
                          collaborationUnit={selectedScene.scene_ref}
                          label="标准场景标题"
                          onChange={(heading) => patchScene({ heading })}
                          value={selectedScene.heading}
                        />
                        <SceneDeckMetadataField
                          collaborationPath={`scenes.${selectedIndex}.location_and_time`}
                          collaborationUnit={selectedScene.scene_ref}
                          label="地点与时间"
                          onChange={(location_and_time) =>
                            patchScene({ location_and_time })
                          }
                          value={selectedScene.location_and_time}
                        />
                      </>
                    ) : (
                      <>
                        <ProductionReadout
                          icon={<Clapperboard size={12} />}
                          label="标准场景标题"
                          value={selectedScene.heading}
                        />
                        <ProductionReadout
                          icon={<MapPin size={12} />}
                          label="地点与时间"
                          value={selectedScene.location_and_time}
                        />
                      </>
                    )}
                  </div>
                  {editable ? (
                    <SceneDeckCastEditor
                      cast={referenceContext.cast}
                      onChange={(cast_subject_refs) =>
                        patchScene({ cast_subject_refs })
                      }
                      scene={selectedScene}
                    />
                  ) : (
                    <div className="scene-deck-cast-readout">
                      <header>
                        <UsersRound size={12} />
                        <span>本场出场人物</span>
                        <small>
                          {selectedScene.cast_subject_refs.length} 人
                        </small>
                      </header>
                      <div>
                        {selectedScene.cast_subject_refs.map((ref) => {
                          const member = referenceContext.cast[ref]
                          return (
                            <span key={ref}>
                              <strong>{member?.label ?? ref}</strong>
                              <small>{member?.role || ref}</small>
                            </span>
                          )
                        })}
                      </div>
                    </div>
                  )}
                  <div className="scene-deck-contract-note">
                    <Film size={13} />
                    <div>
                      <strong>场景只记录可见调度</strong>
                      <p>
                        心理解释、摄影分镜和对白正文不在本阶段写入；Script
                        将从本场目标、对抗和结果生成规范块。
                      </p>
                    </div>
                  </div>
                </div>
              )}
            </section>
          ) : null}
        </main>
      </div>

      <aside className="scene-deck-inspector" aria-label="Scene Deck 检查器">
        <section>
          <span>容量检查</span>
          <dl>
            <div>
              <dt>场次</dt>
              <dd>{diagnostics.sceneCount}</dd>
            </div>
            <div>
              <dt>总页数</dt>
              <dd>{formatPageTarget(diagnostics.totalPageTarget)}</dd>
            </div>
            <div>
              <dt>均场</dt>
              <dd>{formatPageTarget(diagnostics.averagePageTarget)}</dd>
            </div>
          </dl>
          <small
            className={diagnostics.unknownCastRefs.length ? "is-warning" : ""}
          >
            {diagnostics.unknownCastRefs.length
              ? `${diagnostics.unknownCastRefs.length} 个 Cast 引用不在已确认名册`
              : "所有出场人物均来自已确认 Cast"}
          </small>
        </section>
        <section>
          <span>人物覆盖</span>
          <div className="scene-deck-cast-coverage">
            {diagnostics.castCoverage.map((item) => (
              <div key={item.ref}>
                <span>
                  {referenceContext.cast[item.ref]?.label ?? item.ref}
                </span>
                <small>{item.count} 场</small>
              </div>
            ))}
          </div>
        </section>
        <section>
          <span>已确认 Beat 上游</span>
          <div className="scene-deck-beat-context">
            {referenceContext.beats.slice(0, 6).map((beat, index) => (
              <div key={beat.beatRef}>
                <code>{String(index + 1).padStart(2, "0")}</code>
                <span>
                  <strong>{beat.dramaticJob}</strong>
                  <small>{beat.decision}</small>
                </span>
              </div>
            ))}
            {referenceContext.beats.length === 0 ? (
              <small>等待读取已确认 Beat Board</small>
            ) : null}
          </div>
          <p>Beat Board 是调度依据；当前 Artifact 未定义逐场 Beat 引用。</p>
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

function BlockingField({
  collaborationPath,
  collaborationUnit,
  editable,
  emphasized = false,
  icon,
  label,
  onChange,
  step,
  value,
}: BlockingFieldProps) {
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
        <SceneDeckTextField
          collaborationPath={collaborationPath}
          collaborationUnit={collaborationUnit}
          emphasized={emphasized}
          label={label}
          onChange={onChange}
          value={value}
        />
      ) : (
        <SceneDeckReadableField
          emphasized={emphasized}
          label={label}
          value={value}
        />
      )}
    </article>
  )
}

function ProductionReadout({
  icon,
  label,
  value,
}: {
  icon: ReactNode
  label: string
  value: string
}) {
  return (
    <div className="scene-deck-production-readout">
      <span>
        {icon}
        {label}
      </span>
      <strong>{value}</strong>
    </div>
  )
}
