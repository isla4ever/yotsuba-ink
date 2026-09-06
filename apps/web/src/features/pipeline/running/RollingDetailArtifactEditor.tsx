import { useEffect, useMemo, useState } from "react"
import {
  BookOpenCheck,
  CircleDot,
  Layers3,
  Link2,
  MapPinned,
  Rows3,
  UsersRound,
} from "lucide-react"
import {
  formatRollingDetailCount,
  reorderDetailChapters,
  reorderDetailScenes,
  rollingDetailDiagnostics,
  type RollingDetailChapterDraft,
  type RollingDetailDraft,
  type RollingDetailReferenceContext,
  type RollingDetailSceneDraft,
  type RollingDetailWindowDraft,
} from "../lib/phase32RollingDetail"
import { shortPhase32ArtifactRef } from "./VolumeArchitectureEditorFields"
import { RollingDetailChapterEditor } from "./RollingDetailChapterEditor"

type Props = {
  artifact: RollingDetailDraft
  artifactRef: string
  allowCastScopeEditing?: boolean
  editable: boolean
  onChange: (value: Record<string, unknown>) => void
  referenceContext: RollingDetailReferenceContext
  revisionLabel: string
}

export function RollingDetailArtifactEditor({
  allowCastScopeEditing = false,
  artifact,
  artifactRef,
  editable,
  onChange,
  referenceContext,
  revisionLabel,
}: Props) {
  const [selectedWindowRef, setSelectedWindowRef] = useState(
    artifact.windows[0]?.window_ref ?? "",
  )
  const initialChapterRef = artifact.windows[0]?.chapters[0]?.chapter_ref ?? ""
  const [selectedChapterRef, setSelectedChapterRef] =
    useState(initialChapterRef)
  const diagnostics = useMemo(
    () => rollingDetailDiagnostics(artifact),
    [artifact],
  )
  const selectedWindow =
    artifact.windows.find(
      (window) => window.window_ref === selectedWindowRef,
    ) ?? artifact.windows[0]
  const selectedChapterIndex = Math.max(
    0,
    selectedWindow?.chapters.findIndex(
      (chapter) => chapter.chapter_ref === selectedChapterRef,
    ) ?? 0,
  )
  const selectedChapter = selectedWindow?.chapters[selectedChapterIndex]

  useEffect(() => {
    if (
      artifact.windows.some((window) => window.window_ref === selectedWindowRef)
    )
      return
    const next = artifact.windows[0]
    setSelectedWindowRef(next?.window_ref ?? "")
    setSelectedChapterRef(next?.chapters[0]?.chapter_ref ?? "")
  }, [artifact.windows, selectedWindowRef])

  useEffect(() => {
    if (
      selectedWindow?.chapters.some(
        (chapter) => chapter.chapter_ref === selectedChapterRef,
      )
    )
      return
    setSelectedChapterRef(selectedWindow?.chapters[0]?.chapter_ref ?? "")
  }, [selectedChapterRef, selectedWindow])

  const changeArtifact = (next: RollingDetailDraft) => onChange(next)
  const patchWindow = (patch: Partial<RollingDetailWindowDraft>) => {
    changeArtifact({
      windows: artifact.windows.map((window) =>
        window.window_ref === selectedWindow.window_ref
          ? { ...window, ...patch }
          : window,
      ),
    })
  }
  const patchChapter = (patch: Partial<RollingDetailChapterDraft>) => {
    patchWindow({
      chapters: selectedWindow.chapters.map((chapter) =>
        chapter.chapter_ref === selectedChapter.chapter_ref
          ? { ...chapter, ...patch }
          : chapter,
      ),
    })
  }
  const patchScene = (
    sceneRef: string,
    patch: Partial<RollingDetailSceneDraft>,
  ) => {
    patchChapter({
      scenes: selectedChapter.scenes.map((scene) =>
        scene.scene_ref === sceneRef ? { ...scene, ...patch } : scene,
      ),
    })
  }
  const chooseWindow = (window: RollingDetailWindowDraft) => {
    setSelectedWindowRef(window.window_ref)
    setSelectedChapterRef(window.chapters[0]?.chapter_ref ?? "")
  }

  return (
    <div
      className={`phase32-detail-workbench artifact-mode-surface ${
        editable ? "is-editing" : "is-viewing"
      }`}
    >
      <nav className="phase32-detail-rail" aria-label="滚动细纲导航">
        <header>
          <div>
            <Layers3 size={13} />
            <span>Window / 章节</span>
          </div>
          <strong>{diagnostics.chapterCount}</strong>
        </header>
        <div className="phase32-detail-rail-content">
          <div className="phase32-detail-window-switcher">
            {artifact.windows.map((window) => (
              <button
                aria-current={
                  selectedWindowRef === window.window_ref ? "step" : undefined
                }
                className={
                  selectedWindowRef === window.window_ref ? "is-active" : ""
                }
                key={window.window_ref}
                onClick={() => chooseWindow(window)}
                type="button"
              >
                W{String(window.ordinal).padStart(2, "0")}
                <span>{window.chapters.length} 章</span>
              </button>
            ))}
          </div>
          <div className="phase32-detail-chapter-list">
            {selectedWindow.chapters.map((chapter) => (
              <button
                aria-current={
                  selectedChapterRef === chapter.chapter_ref
                    ? "step"
                    : undefined
                }
                className={
                  selectedChapterRef === chapter.chapter_ref ? "is-active" : ""
                }
                key={chapter.chapter_ref}
                onClick={() => setSelectedChapterRef(chapter.chapter_ref)}
                type="button"
              >
                <span>{String(chapter.ordinal).padStart(2, "0")}</span>
                <span>
                  <strong>{chapter.title}</strong>
                  <small>{chapter.dramatic_job}</small>
                  <i>
                    {referenceContext.cast[chapter.pov_subject_ref]?.label ??
                      chapter.pov_subject_ref}
                    <b>{chapter.scenes.length} 场</b>
                  </i>
                </span>
                <em aria-hidden="true" />
              </button>
            ))}
          </div>
        </div>
        <footer>
          <Link2 size={12} />
          <span>Window、章节、场景与上游引用随候选冻结</span>
        </footer>
      </nav>

      <div className="phase32-detail-scroll">
        <div className="phase32-detail-mobile-nav" aria-label="章节快捷导航">
          {selectedWindow.chapters.map((chapter) => (
            <button
              className={
                selectedChapterRef === chapter.chapter_ref ? "is-active" : ""
              }
              key={chapter.chapter_ref}
              onClick={() => setSelectedChapterRef(chapter.chapter_ref)}
              type="button"
            >
              C{String(chapter.ordinal).padStart(2, "0")}
            </button>
          ))}
        </div>

        <main className="phase32-detail-canvas">
          <header className="phase32-detail-heading">
            <div>
              <span>LONG NOVEL · ROLLING DETAIL</span>
              <h1>当前窗口章节施工账本</h1>
            </div>
            <p>只规划当前有界窗口，把可执行状态连续交给正文与下一 Window。</p>
          </header>

          <section className="phase32-detail-window-handoff">
            <header>
              <div>
                <MapPinned size={12} />
                <strong>
                  Window {String(selectedWindow.ordinal).padStart(2, "0")}
                </strong>
                <code>{selectedWindow.window_ref}</code>
              </div>
              <span>{selectedWindow.chapters.length} 章</span>
            </header>
            <div>
              <WindowField
                editable={editable}
                label="进入状态"
                value={selectedWindow.entry_state}
                onChange={(entry_state) => patchWindow({ entry_state })}
              />
              <WindowField
                editable={editable}
                label="窗口交接"
                value={selectedWindow.handoff}
                onChange={(handoff) => patchWindow({ handoff })}
              />
              <WindowField
                editable={editable}
                label="下一窗口入口"
                value={selectedWindow.next_window_entry_state}
                onChange={(next_window_entry_state) =>
                  patchWindow({ next_window_entry_state })
                }
              />
            </div>
          </section>

          <section className="phase32-detail-ledger" aria-label="章节施工账本">
            <header>
              <span>章节</span>
              <span>戏剧任务</span>
              <span>POV / 场景</span>
              <span>交接</span>
              <span>预算</span>
            </header>
            <div>
              {selectedWindow.chapters.map((chapter) => (
                <button
                  className={
                    selectedChapterRef === chapter.chapter_ref
                      ? "is-active"
                      : ""
                  }
                  key={chapter.chapter_ref}
                  onClick={() => setSelectedChapterRef(chapter.chapter_ref)}
                  type="button"
                >
                  <span>
                    <i>{String(chapter.ordinal).padStart(2, "0")}</i>
                    <strong>{chapter.title}</strong>
                  </span>
                  <span>{chapter.dramatic_job}</span>
                  <span>
                    {referenceContext.cast[chapter.pov_subject_ref]?.label ??
                      chapter.pov_subject_ref}
                    <small>{chapter.scenes.length} 场</small>
                  </span>
                  <span>{chapter.handoff}</span>
                  <span>{formatRollingDetailCount(chapter.length_hint)}</span>
                </button>
              ))}
            </div>
          </section>

          {selectedChapter ? (
            <RollingDetailChapterEditor
              allowCastScopeEditing={allowCastScopeEditing}
              chapter={selectedChapter}
              chapterCount={selectedWindow.chapters.length}
              chapterIndex={selectedChapterIndex}
              editable={editable}
              onMoveChapter={(offset) =>
                changeArtifact(
                  reorderDetailChapters(
                    artifact,
                    selectedWindow.window_ref,
                    selectedChapterIndex,
                    offset,
                  ),
                )
              }
              onMoveScene={(sceneIndex, offset) =>
                patchChapter({
                  scenes: reorderDetailScenes(
                    selectedChapter.scenes,
                    sceneIndex,
                    offset,
                  ),
                })
              }
              onPatchChapter={patchChapter}
              onPatchScene={patchScene}
              referenceContext={referenceContext}
            />
          ) : null}
        </main>
      </div>

      <aside className="phase32-detail-inspector" aria-label="滚动细纲检查器">
        <section className="phase32-detail-inspector-stats">
          <div>
            <strong>{diagnostics.windowCount}</strong>
            <span>Window</span>
          </div>
          <div>
            <strong>{diagnostics.chapterCount}</strong>
            <span>章节</span>
          </div>
          <div>
            <strong>{diagnostics.sceneCount}</strong>
            <span>场景</span>
          </div>
        </section>
        <section>
          <span>Volume 覆盖</span>
          <div className="phase32-detail-coverage">
            {diagnostics.volumeCoverage.map((item) => (
              <div key={item.volumeRef}>
                <strong>
                  {referenceContext.volumes[item.volumeRef]?.label ??
                    item.volumeRef}
                </strong>
                <small>
                  {item.chapterCount} 章 ·{" "}
                  {formatRollingDetailCount(item.lengthHint)} 字
                </small>
              </div>
            ))}
          </div>
        </section>
        <section>
          <span>当前章节</span>
          <p>{selectedChapter?.title}</p>
          <small>
            <UsersRound size={11} />
            {selectedChapter?.cast_subject_refs
              .map((ref) => referenceContext.cast[ref]?.label ?? ref)
              .join(" · ")}
          </small>
          <small>
            <Rows3 size={11} /> {selectedChapter?.scenes.length ?? 0}{" "}
            个场景施工单元
          </small>
        </section>
        <section>
          <span>编辑边界</span>
          <p>
            {allowCastScopeEditing
              ? "可修改文学字段与局部人物范围，稳定身份保持冻结。"
              : "可修改文学字段、软篇幅，并重排冻结章节与场景。"}
          </p>
          <small>
            {allowCastScopeEditing
              ? "人物只能取自当前 Volume；Scene 人物必须属于 Chapter。"
              : "新增人物、章节、场景或改变 Volume/POV 范围需走 amendment。"}
          </small>
        </section>
        <section>
          <span>下游交接</span>
          <p>
            <BookOpenCheck size={11} /> Text 只读取当前章节蓝图、相关人物与上一
            handoff。
          </p>
          <small>Wiki、Canon 与事实候选仍由各自 sidecar 管理。</small>
        </section>
        <section>
          <span>版本来源</span>
          <code title={artifactRef}>
            {shortPhase32ArtifactRef(artifactRef)}
          </code>
          <small>{revisionLabel}</small>
          <small>
            {editable
              ? "全部 Window 随当前聚合草稿一次保存。"
              : "当前为稳定阅读视图。"}
          </small>
        </section>
      </aside>
    </div>
  )
}

function WindowField({
  editable,
  label,
  onChange,
  value,
}: {
  editable: boolean
  label: string
  onChange: (value: string) => void
  value: string
}) {
  if (!editable) {
    return (
      <div className="phase32-detail-window-readout artifact-readable-field">
        <span>
          <CircleDot size={10} /> {label}
        </span>
        <p className="artifact-readable-value">{value}</p>
      </div>
    )
  }
  return (
    <label>
      <span>
        <CircleDot size={10} /> {label}
      </span>
      <textarea
        readOnly={!editable}
        rows={3}
        value={value}
        onChange={(event) => onChange(event.target.value)}
      />
    </label>
  )
}
