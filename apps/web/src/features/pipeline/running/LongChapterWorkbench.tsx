import { useEffect, useMemo, useState } from "react"
import {
  ArrowRight,
  BadgeCheck,
  BookMarked,
  CircleDashed,
  FileText,
  Gauge,
  Layers3,
  Link2,
  LockKeyhole,
  MapPinned,
  Route,
  Target,
  UserRound,
} from "lucide-react"
import {
  longChapterDiagnostics,
  longChapterParagraphs,
  type LongChapterContext,
  type LongChapterDraft,
} from "../lib/phase32LongChapter"

type Props = {
  activeChapterRef: string
  artifact: LongChapterDraft | null
  artifactRef: string
  committedArtifactRefs: Record<string, string>
  editable: boolean
  onChange: (value: Record<string, unknown>) => void
  onSelectChapter: (chapterRef: string) => void
  orderedChapterRefs: string[]
  referenceContext: LongChapterContext
  revisionLabel: string
  selectedChapterRef: string
}

type InspectorSection = "plan" | "continuity" | "sources"

export function LongChapterWorkbench({
  activeChapterRef,
  artifact,
  artifactRef,
  committedArtifactRefs,
  editable,
  onChange,
  onSelectChapter,
  orderedChapterRefs,
  referenceContext,
  revisionLabel,
  selectedChapterRef,
}: Props) {
  const [inspectorSection, setInspectorSection] =
    useState<InspectorSection>("plan")
  const chapterByRef = useMemo(
    () =>
      Object.fromEntries(
        referenceContext.chapters.map((chapter) => [
          chapter.chapterRef,
          chapter,
        ]),
      ),
    [referenceContext.chapters],
  )
  const volumeGroups = useMemo(() => {
    const result: Array<{
      volumeRef: string
      chapterRefs: string[]
    }> = []
    for (const chapterRef of orderedChapterRefs) {
      const volumeRef = chapterByRef[chapterRef]?.volumeRef || "unassigned"
      const group = result.find((item) => item.volumeRef === volumeRef)
      if (group) group.chapterRefs.push(chapterRef)
      else result.push({ chapterRefs: [chapterRef], volumeRef })
    }
    return result
  }, [chapterByRef, orderedChapterRefs])
  const selectedIndex = Math.max(
    0,
    orderedChapterRefs.indexOf(selectedChapterRef),
  )
  const selectedChapter = chapterByRef[selectedChapterRef]
  const previousChapter = chapterByRef[orderedChapterRefs[selectedIndex - 1]]
  const nextChapter = chapterByRef[orderedChapterRefs[selectedIndex + 1]]
  const selectedVolume = selectedChapter
    ? referenceContext.volumes[selectedChapter.volumeRef]
    : undefined
  const selectedPart = selectedVolume
    ? referenceContext.parts[selectedVolume.partRef]
    : undefined
  const pov = selectedChapter
    ? referenceContext.cast[selectedChapter.povSubjectRef]
    : undefined
  const diagnostics = artifact
    ? longChapterDiagnostics(artifact, selectedChapter)
    : null
  const paragraphs = artifact ? longChapterParagraphs(artifact.content) : []
  const previousCommittedRef = previousChapter
    ? committedArtifactRefs[previousChapter.chapterRef]
    : ""

  useEffect(() => setInspectorSection("plan"), [selectedChapterRef])

  return (
    <div
      className={`long-chapter-workbench artifact-mode-surface ${
        editable ? "is-editing" : "is-viewing"
      }`}
    >
      <nav className="long-chapter-rail" aria-label="长篇章节导航">
        <header>
          <div>
            <BookMarked size={13} />
            <span>卷章目录</span>
          </div>
          <strong>
            {Object.keys(committedArtifactRefs).length}/
            {orderedChapterRefs.length}
          </strong>
        </header>
        <div className="long-chapter-rail-tree">
          {volumeGroups.map((group) => {
            const volume = referenceContext.volumes[group.volumeRef]
            return (
              <section key={group.volumeRef}>
                <header>
                  <span>V{String(volume?.ordinal ?? 0).padStart(2, "0")}</span>
                  <strong>{volume?.promise || group.volumeRef}</strong>
                </header>
                {group.chapterRefs.map((chapterRef) => {
                  const chapter = chapterByRef[chapterRef]
                  const status = committedArtifactRefs[chapterRef]
                    ? "accepted"
                    : chapterRef === activeChapterRef
                      ? "current"
                      : "queued"
                  return (
                    <button
                      aria-current={
                        selectedChapterRef === chapterRef ? "step" : undefined
                      }
                      className={`${
                        selectedChapterRef === chapterRef ? "is-active" : ""
                      } is-${status}`}
                      key={chapterRef}
                      onClick={() => onSelectChapter(chapterRef)}
                      type="button"
                    >
                      <span>
                        {String(chapter?.ordinal ?? 0).padStart(2, "0")}
                      </span>
                      <span>
                        <strong>{chapter?.title || chapterRef}</strong>
                        <small>
                          {chapter
                            ? referenceContext.cast[chapter.povSubjectRef]
                                ?.displayName || chapter.povSubjectRef
                            : chapterRef}
                        </small>
                      </span>
                      <i>{statusLabel(status)}</i>
                    </button>
                  )
                })}
              </section>
            )
          })}
        </div>
        <footer>
          <LockKeyhole size={12} />
          <span>接受章只读；当前候选可编辑</span>
        </footer>
      </nav>

      <div className="long-chapter-scroll">
        <div className="long-chapter-mobile-nav" aria-label="章节快捷导航">
          {orderedChapterRefs.map((chapterRef, index) => (
            <button
              className={selectedChapterRef === chapterRef ? "is-active" : ""}
              key={chapterRef}
              onClick={() => onSelectChapter(chapterRef)}
              type="button"
            >
              {String(index + 1).padStart(2, "0")}
            </button>
          ))}
        </div>

        <main className="long-chapter-canvas">
          <header className="long-chapter-heading">
            <div>
              <span>LONG NOVEL · CHAPTER MANUSCRIPT</span>
              <h1>逐章正文工作台</h1>
            </div>
            <p>章节按冻结细纲顺序推进；历史接受版本不参与覆盖式编辑。</p>
          </header>

          <article className="long-chapter-sheet">
            <header className="long-chapter-sheet-header">
              <div>
                <span>{String(selectedIndex + 1).padStart(2, "0")}</span>
                <div>
                  <small>
                    PART {String(selectedPart?.ordinal ?? 0).padStart(2, "0")} ·
                    VOL {String(selectedVolume?.ordinal ?? 0).padStart(2, "0")}
                  </small>
                  <strong>{selectedChapter?.title || "等待章节正文"}</strong>
                  <code>{selectedChapterRef}</code>
                </div>
              </div>
              <div className="long-chapter-sheet-meta">
                <span>{revisionLabel}</span>
                <span>
                  {diagnostics
                    ? `${diagnostics.characterCount.toLocaleString("zh-CN")} 字`
                    : "尚未生成"}
                </span>
              </div>
            </header>

            {artifact ? (
              editable ? (
                <label className="long-chapter-editor page-in">
                  <span>当前候选正文</span>
                  <textarea
                    aria-label="当前章节正文"
                    autoFocus
                    data-collaboration-field-path="content"
                    data-collaboration-unit={selectedChapterRef}
                    onChange={(event) =>
                      onChange({ ...artifact, content: event.target.value })
                    }
                    spellCheck={false}
                    value={artifact.content}
                  />
                </label>
              ) : (
                <div className="long-chapter-manuscript page-in">
                  {paragraphs.map((paragraph, index) => (
                    <p key={`${index}-${paragraph.slice(0, 18)}`}>
                      {paragraph}
                    </p>
                  ))}
                </div>
              )
            ) : (
              <div className="long-chapter-sheet-empty">
                <CircleDashed size={20} />
                <strong>该章尚未进入正文生成</strong>
                <p>前章接受后，系统会绑定其交接和有限正文尾部继续写作。</p>
              </div>
            )}

            <footer className="long-chapter-sheet-footer">
              <span>
                <FileText size={11} />
                {diagnostics?.paragraphCount ?? 0} 个自然段
              </span>
              <code>{shortRef(artifactRef)}</code>
            </footer>
          </article>
        </main>
      </div>

      <aside className="long-chapter-inspector">
        <header>
          <div>
            <Route size={13} />
            <strong>章节上下文</strong>
          </div>
          <div className="long-chapter-inspector-tabs">
            {([
              ["plan", "计划"],
              ["continuity", "交接"],
              ["sources", "来源"],
            ] as const).map(([value, label]) => (
              <button
                aria-pressed={inspectorSection === value}
                className={inspectorSection === value ? "is-active" : ""}
                key={value}
                onClick={() => setInspectorSection(value)}
                type="button"
              >
                {label}
              </button>
            ))}
          </div>
        </header>

        {inspectorSection === "plan" ? (
          <div className="long-chapter-inspector-body page-in">
            <section className="is-lead">
              <span>
                <Target size={11} /> 戏剧任务
              </span>
              <p>{selectedChapter?.dramaticJob || "等待冻结章节计划"}</p>
            </section>
            <section>
              <span>
                <UserRound size={11} /> POV 与声音
              </span>
              <strong>
                {pov?.displayName || selectedChapter?.povSubjectRef || "-"}
              </strong>
              <small>{pov?.role || "人物职责来自已确认 Cast"}</small>
              {pov?.voice ? <p>{pov.voice}</p> : null}
            </section>
            <section>
              <span>
                <Gauge size={11} /> 章节软字数
              </span>
              <div className="long-chapter-budget">
                <strong>
                  {(diagnostics?.characterCount ?? 0).toLocaleString("zh-CN")}
                </strong>
                <small>
                  / {(selectedChapter?.lengthHint ?? 0).toLocaleString("zh-CN")}{" "}
                  字
                </small>
              </div>
              <div className="long-chapter-budget-track">
                <span
                  style={{
                    width: `${Math.min(100, Math.max(0, (diagnostics?.budgetRatio ?? 0) * 100))}%`,
                  }}
                />
              </div>
            </section>
            <section>
              <span>
                <Layers3 size={11} /> 场景施工
              </span>
              {selectedChapter?.scenes.map((scene) => (
                <div className="long-chapter-scene" key={scene.sceneRef}>
                  <strong>{scene.location}</strong>
                  <small>{scene.timeContext}</small>
                  <p>{scene.goal}</p>
                </div>
              ))}
            </section>
          </div>
        ) : inspectorSection === "continuity" ? (
          <div className="long-chapter-inspector-body page-in">
            <section>
              <span>
                <Link2 size={11} /> 上一章交接
              </span>
              <p>
                {previousChapter?.handoff ||
                  selectedPart?.entryState ||
                  "从当前 Part 入口状态开始。"}
              </p>
              <small className={previousCommittedRef ? "is-bound" : ""}>
                {!previousChapter
                  ? "首章无需相邻正文"
                  : previousCommittedRef
                    ? "已绑定上一章不可变版本与有限正文尾部"
                    : "等待上一章接受"}
              </small>
            </section>
            <section>
              <span>本章状态迁移</span>
              <p>{selectedChapter?.entryState || "-"}</p>
              <ArrowRight size={12} />
              <p>{selectedChapter?.exitState || "-"}</p>
            </section>
            <section className="long-chapter-receipt">
              <span>
                <BadgeCheck size={11} /> 连续性回执
              </span>
              <dl>
                <div>
                  <dt>细纲身份</dt>
                  <dd>{selectedChapter ? "已冻结" : "未就绪"}</dd>
                </div>
                <div>
                  <dt>卷 / Part</dt>
                  <dd>
                    {selectedVolume && selectedPart ? "已绑定" : "待核验"}
                  </dd>
                </div>
                <div>
                  <dt>前章版本</dt>
                  <dd>
                    {!previousChapter || previousCommittedRef
                      ? "已绑定"
                      : "等待前序"}
                  </dd>
                </div>
              </dl>
            </section>
            {nextChapter ? (
              <section className="long-chapter-next">
                <span>下一章</span>
                <strong>{nextChapter.title}</strong>
                <p>{nextChapter.dramaticJob}</p>
              </section>
            ) : null}
          </div>
        ) : (
          <div className="long-chapter-inspector-body page-in">
            <section className="is-lead">
              <span>
                <BookMarked size={11} /> 全书承诺
              </span>
              <p>{referenceContext.bookPromise || "等待全书架构"}</p>
            </section>
            <section>
              <span>
                <MapPinned size={11} /> 当前 Part
              </span>
              <p>{selectedPart?.dramaticQuestion || "-"}</p>
              <small>{selectedVolume?.partRef || "未绑定"}</small>
            </section>
            <section>
              <span>当前卷合同</span>
              <strong>{selectedVolume?.promise || "-"}</strong>
              <p>{selectedVolume?.conflict || "-"}</p>
            </section>
            <section>
              <span>章节冲突 / 风险 / 钩子</span>
              <p>{selectedChapter?.conflict || "-"}</p>
              <p>{selectedChapter?.stakes || "-"}</p>
              <p>{selectedChapter?.hook || "-"}</p>
            </section>
          </div>
        )}
      </aside>
    </div>
  )
}

function statusLabel(status: "accepted" | "current" | "queued") {
  return { accepted: "已接受", current: "当前", queued: "等待" }[status]
}

function shortRef(value: string) {
  if (!value) return "NO ARTIFACT"
  return value.length > 34 ? `${value.slice(0, 22)}…${value.slice(-8)}` : value
}
