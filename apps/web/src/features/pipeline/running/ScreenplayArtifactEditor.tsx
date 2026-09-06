import { useMemo, useState } from "react"
import {
  ArrowRight,
  BadgeCheck,
  CircleDashed,
  Clapperboard,
  FileText,
  LockKeyhole,
  MessageSquareText,
  Radio,
  UsersRound,
} from "lucide-react"
import {
  screenplayContractError,
  screenplayDiagnostics,
  shortSceneRef,
  type ScreenplayBlockDraft,
  type ScreenplayDraft,
  type ScreenplayReferenceContext,
} from "../lib/phase32Screenplay"
import { ScreenplayBlockEditor } from "./ScreenplayBlockEditor"

type Props = {
  activeSceneRef: string
  artifact: ScreenplayDraft | null
  artifactRef: string
  committedArtifactRefs: Record<string, string>
  editable: boolean
  onChange: (value: Record<string, unknown>) => void
  onSelectScene: (sceneRef: string) => void
  orderedSceneRefs: string[]
  referenceContext: ScreenplayReferenceContext
  revisionLabel: string
  selectedSceneRef: string
}

type Section = "page" | "schedule"

export function ScreenplayArtifactEditor({
  activeSceneRef,
  artifact,
  artifactRef,
  committedArtifactRefs,
  editable,
  onChange,
  onSelectScene,
  orderedSceneRefs,
  referenceContext,
  revisionLabel,
  selectedSceneRef,
}: Props) {
  const [section, setSection] = useState<Section>("page")
  const sceneByRef = useMemo(
    () =>
      Object.fromEntries(
        referenceContext.scenes.map((scene) => [scene.sceneRef, scene]),
      ),
    [referenceContext.scenes],
  )
  const selectedIndex = Math.max(0, orderedSceneRefs.indexOf(selectedSceneRef))
  const selectedScene = sceneByRef[selectedSceneRef]
  const previousScene = sceneByRef[orderedSceneRefs[selectedIndex - 1]]
  const diagnostics = artifact
    ? screenplayDiagnostics(artifact, referenceContext)
    : null
  const contractError = screenplayContractError(artifact, referenceContext)
  const patchBlocks = (blocks: ScreenplayBlockDraft[]) => {
    if (!artifact) return
    onChange({ scene_ref: artifact.scene_ref, blocks })
  }

  return (
    <div
      className={`screenplay-workbench artifact-mode-surface ${
        editable ? "is-editing" : "is-viewing"
      }`}
    >
      <nav className="screenplay-rail" aria-label="剧本场景导航">
        <header>
          <div>
            <Clapperboard size={13} />
            <span>剧本场次</span>
          </div>
          <strong>
            {Object.keys(committedArtifactRefs).length}/
            {orderedSceneRefs.length}
          </strong>
        </header>
        <div className="screenplay-rail-list">
          {orderedSceneRefs.map((sceneRef, index) => {
            const scene = sceneByRef[sceneRef]
            const status = committedArtifactRefs[sceneRef]
              ? "accepted"
              : sceneRef === activeSceneRef
                ? "current"
                : "queued"
            return (
              <button
                aria-current={
                  selectedSceneRef === sceneRef ? "step" : undefined
                }
                className={`${
                  selectedSceneRef === sceneRef ? "is-active" : ""
                } is-${status}`}
                key={sceneRef}
                onClick={() => {
                  onSelectScene(sceneRef)
                  setSection("page")
                }}
                type="button"
              >
                <span>{String(index + 1).padStart(2, "0")}</span>
                <span>
                  <strong>{scene?.heading || shortSceneRef(sceneRef)}</strong>
                  <small>{scene?.locationAndTime || sceneRef}</small>
                  <i>{statusLabel(status)}</i>
                </span>
                <em aria-hidden="true" />
              </button>
            )
          })}
        </div>
        <footer>
          <LockKeyhole size={12} />
          <span>已接受场次保持不可变；正文严格按 Scene 顺序推进</span>
        </footer>
      </nav>

      <div className="screenplay-scroll">
        <div className="screenplay-mobile-nav" aria-label="剧本场次快捷导航">
          {orderedSceneRefs.map((sceneRef, index) => (
            <button
              className={selectedSceneRef === sceneRef ? "is-active" : ""}
              key={sceneRef}
              onClick={() => onSelectScene(sceneRef)}
              type="button"
            >
              S{String(index + 1).padStart(2, "0")}
            </button>
          ))}
        </div>
        <main className="screenplay-canvas">
          <header className="screenplay-heading">
            <div>
              <span>SCREENPLAY SAMPLE · DRAFT</span>
              <h1>剧本正文</h1>
            </div>
            <p>
              逐场确认可拍摄正文；当前场只继承冻结调度、相关人物与已接受前缀。
            </p>
          </header>

          <section className="screenplay-sheet">
            <header className="screenplay-sheet-header">
              <div>
                <span>{String(selectedIndex + 1).padStart(2, "0")}</span>
                <div>
                  <small>当前场次</small>
                  <strong>
                    {selectedScene?.heading || shortSceneRef(selectedSceneRef)}
                  </strong>
                  <code>{selectedSceneRef}</code>
                </div>
              </div>
              <div className="screenplay-sheet-meta">
                <span>{selectedScene?.softPageTarget || "-"} P</span>
                <span>{selectedScene?.castSubjectRefs.length || 0} CAST</span>
              </div>
            </header>

            <div className="artifact-section-tabs" role="tablist">
              <button
                aria-selected={section === "page"}
                className={section === "page" ? "is-active" : ""}
                onClick={() => setSection("page")}
                role="tab"
                type="button"
              >
                <FileText size={12} /> 剧本页 <span>01</span>
              </button>
              <button
                aria-selected={section === "schedule"}
                className={section === "schedule" ? "is-active" : ""}
                onClick={() => setSection("schedule")}
                role="tab"
                type="button"
              >
                <Radio size={12} /> 调度依据 <span>02</span>
              </button>
            </div>

            {section === "page" ? (
              artifact ? (
                editable ? (
                  <ScreenplayBlockEditor
                    blocks={artifact.blocks}
                    cast={referenceContext.cast}
                    onChange={patchBlocks}
                    sceneRef={selectedSceneRef}
                    sceneCastRefs={selectedScene?.castSubjectRefs ?? []}
                  />
                ) : (
                  <ScreenplayPage
                    artifact={artifact}
                    cast={referenceContext.cast}
                  />
                )
              ) : (
                <div className="screenplay-queued-state">
                  <CircleDashed size={20} />
                  <strong>本场正文尚未生成</strong>
                  <p>
                    确认前序场次后，系统会携带上一场交接与已接受版本自动进入本场。
                  </p>
                </div>
              )
            ) : (
              <div className="screenplay-schedule" role="tabpanel">
                <ScheduleBand
                  label="上一场结果"
                  value={previousScene?.outcome || "样片从本场进入可见行动。"}
                />
                <ArrowRight aria-hidden="true" size={16} />
                <ScheduleBand
                  emphasized
                  label="本场目标"
                  value={selectedScene?.visibleGoal || "等待读取冻结调度"}
                />
                <ArrowRight aria-hidden="true" size={16} />
                <ScheduleBand
                  label="台面对抗"
                  value={selectedScene?.opposition || "等待读取冻结调度"}
                />
                <div className="screenplay-schedule-outcome">
                  <BadgeCheck size={13} />
                  <span>必须落地的场景结果</span>
                  <p>{selectedScene?.outcome || "等待读取冻结调度"}</p>
                </div>
              </div>
            )}
          </section>
        </main>
      </div>

      <aside className="screenplay-inspector" aria-label="剧本正文检查器">
        <section>
          <span>场景进度</span>
          <dl>
            <div>
              <dt>已接受</dt>
              <dd>{Object.keys(committedArtifactRefs).length}</dd>
            </div>
            <div>
              <dt>总场次</dt>
              <dd>{orderedSceneRefs.length}</dd>
            </div>
            <div>
              <dt>正文块</dt>
              <dd>{diagnostics?.blockCount ?? 0}</dd>
            </div>
          </dl>
        </section>
        <section>
          <span>当前场人物</span>
          <div className="screenplay-cast-list">
            {(selectedScene?.castSubjectRefs ?? []).map((ref) => (
              <div key={ref}>
                <UsersRound size={11} />
                <span>
                  <strong>
                    {referenceContext.cast[ref]?.displayName ?? ref}
                  </strong>
                  <small>{referenceContext.cast[ref]?.role || ref}</small>
                </span>
              </div>
            ))}
          </div>
          <small className={contractError ? "is-warning" : ""}>
            {diagnostics?.unknownSpeakerRefs.length
              ? `${diagnostics.unknownSpeakerRefs.length} 个对白人物不在已确认 Cast`
              : diagnostics?.outOfSceneSpeakerRefs.length
                ? `${diagnostics.outOfSceneSpeakerRefs.length} 个对白人物不在本场冻结范围`
                : diagnostics && !diagnostics.sceneHeadingMatches
                  ? "场景标题与冻结调度不一致"
                  : "对白人物与标题均符合本场冻结合同"}
          </small>
        </section>
        <section>
          <span>块结构</span>
          <div className="screenplay-block-counts">
            <span>
              <MessageSquareText size={11} /> 对白{" "}
              {diagnostics?.dialogueBlocks ?? 0}
            </span>
            <span>
              <Clapperboard size={11} /> 动作 {diagnostics?.actionBlocks ?? 0}
            </span>
          </div>
        </section>
        <section>
          <span>Scene 版本</span>
          <code>{artifactRef || "等待生成"}</code>
          <small>{revisionLabel}</small>
        </section>
      </aside>
    </div>
  )
}

function ScreenplayPage({
  artifact,
  cast,
}: {
  artifact: ScreenplayDraft
  cast: ScreenplayReferenceContext["cast"]
}) {
  return (
    <div className="screenplay-page" role="document">
      {artifact.blocks.map((block, index) => (
        <div
          className={`screenplay-block kind-${block.kind}`}
          key={`${index}-${block.kind}`}
        >
          {block.kind === "dialogue" ? (
            <strong>
              {cast[block.speaker_ref ?? ""]?.displayName ?? block.speaker_ref}
            </strong>
          ) : null}
          <p>{block.text}</p>
        </div>
      ))}
    </div>
  )
}

function ScheduleBand({
  emphasized = false,
  label,
  value,
}: {
  emphasized?: boolean
  label: string
  value: string
}) {
  return (
    <div className={emphasized ? "is-emphasized" : ""}>
      <span>{label}</span>
      <p>{value}</p>
    </div>
  )
}

function statusLabel(status: "accepted" | "current" | "queued") {
  return {
    accepted: "已接受版本",
    current: "当前候选",
    queued: "等待前序场次",
  }[status]
}
