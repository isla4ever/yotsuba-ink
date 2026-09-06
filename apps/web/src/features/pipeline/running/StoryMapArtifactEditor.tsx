import { useEffect, useMemo, useState } from "react"
import {
  ArrowDown,
  ArrowUp,
  CircleHelp,
  Flag,
  GitBranch,
  Link2,
  MapPinned,
  Plus,
  Trash2,
} from "lucide-react"
import {
  storyMapDiagnostics,
  type StoryMapAnchorDraft,
  type StoryMapDraft,
} from "../lib/phase32StoryMap"

type Props = {
  artifact: StoryMapDraft
  artifactRef: string
  editable: boolean
  revisionLabel: string
  onChange: (value: Record<string, unknown>) => void
}

type StoryMapSection = "opening" | "anchor" | "ending"

export function StoryMapArtifactEditor({
  artifact,
  artifactRef,
  editable,
  revisionLabel,
  onChange,
}: Props) {
  const [selectedAnchorRef, setSelectedAnchorRef] = useState(
    artifact.anchors[0]?.anchor_ref ?? "",
  )
  const [section, setSection] = useState<StoryMapSection>("anchor")
  const [newQuestion, setNewQuestion] = useState("")
  const diagnostics = useMemo(() => storyMapDiagnostics(artifact), [artifact])
  const selectedIndex = Math.max(
    0,
    artifact.anchors.findIndex(
      (anchor) => anchor.anchor_ref === selectedAnchorRef,
    ),
  )

  useEffect(() => {
    if (
      artifact.anchors.some((anchor) => anchor.anchor_ref === selectedAnchorRef)
    )
      return
    setSelectedAnchorRef(artifact.anchors[0]?.anchor_ref ?? "")
  }, [artifact.anchors, selectedAnchorRef])

  const patch = (value: Partial<StoryMapDraft>) =>
    onChange({ ...artifact, ...value })

  const patchAnchor = (index: number, value: Partial<StoryMapAnchorDraft>) => {
    const anchors = artifact.anchors.map((anchor, anchorIndex) =>
      anchorIndex === index ? { ...anchor, ...value } : anchor,
    )
    patch({ anchors })
  }

  const moveAnchor = (index: number, offset: -1 | 1) => {
    const target = index + offset
    if (target < 0 || target >= artifact.anchors.length) return
    const anchors = [...artifact.anchors]
    ;[anchors[index], anchors[target]] = [anchors[target], anchors[index]]
    patch({ anchors })
  }

  const selectAnchor = (anchorRef: string) => {
    setSelectedAnchorRef(anchorRef)
    setSection("anchor")
  }

  const patchQuestion = (index: number, value: string) => {
    const openQuestions = artifact.open_questions.map(
      (question, questionIndex) => (questionIndex === index ? value : question),
    )
    patch({ open_questions: openQuestions })
  }

  const removeQuestion = (index: number) => {
    patch({
      open_questions: artifact.open_questions.filter(
        (_, questionIndex) => questionIndex !== index,
      ),
    })
  }

  const addQuestion = () => {
    const question = newQuestion.trim()
    if (!question) return
    patch({ open_questions: [...artifact.open_questions, question] })
    setNewQuestion("")
  }

  return (
    <div
      className={`story-map-workbench artifact-mode-surface ${
        editable ? "is-editing" : "is-viewing"
      }`}
    >
      <nav className="story-map-anchor-rail" aria-label="故事锚点导航">
        <header>
          <div>
            <MapPinned size={13} />
            <span>故事锚点</span>
          </div>
          <strong>{artifact.anchors.length}</strong>
        </header>
        <div className="story-map-anchor-list">
          {artifact.anchors.map((anchor, index) => (
            <button
              type="button"
              key={anchor.anchor_ref}
              className={
                selectedAnchorRef === anchor.anchor_ref ? "is-active" : ""
              }
              aria-current={
                selectedAnchorRef === anchor.anchor_ref ? "step" : undefined
              }
              onClick={() => selectAnchor(anchor.anchor_ref)}
            >
              <span>{String(index + 1).padStart(2, "0")}</span>
              <span>
                <strong>{anchor.dramatic_job}</strong>
                <small>{anchor.consequence_or_open_effect}</small>
              </span>
              <i aria-hidden="true" />
            </button>
          ))}
        </div>
        <footer>
          <GitBranch size={12} />
          <span>锚点顺序随当前稿一次保存</span>
        </footer>
      </nav>

      <div className="story-map-scroll">
        <div
          className="story-map-mobile-anchor-list"
          aria-label="故事锚点快捷导航"
        >
          {artifact.anchors.map((anchor, index) => (
            <button
              type="button"
              key={anchor.anchor_ref}
              className={
                selectedAnchorRef === anchor.anchor_ref ? "is-active" : ""
              }
              onClick={() => selectAnchor(anchor.anchor_ref)}
            >
              {String(index + 1).padStart(2, "0")}
            </button>
          ))}
        </div>

        <main className="story-map-canvas">
          <header className="story-map-heading">
            <div>
              <span>SHORT NOVEL · STORY MAP</span>
              <h1>从开场压力到结尾状态</h1>
            </div>
            <p>编辑选择、揭示与后果；引用标识由系统保持稳定。</p>
          </header>

          <nav className="artifact-section-tabs" aria-label="故事地图分区">
            <button
              className={section === "opening" ? "is-active" : ""}
              onClick={() => setSection("opening")}
              type="button"
            >
              开场与问题
            </button>
            <button
              className={section === "anchor" ? "is-active" : ""}
              onClick={() => setSection("anchor")}
              type="button"
            >
              当前故事锚点
              <span>{String(selectedIndex + 1).padStart(2, "0")}</span>
            </button>
            <button
              className={section === "ending" ? "is-active" : ""}
              onClick={() => setSection("ending")}
              type="button"
            >
              收束与追问
            </button>
          </nav>

          {section === "opening" ? (
            <section className="story-map-boundary is-opening">
              <div className="story-map-boundary-label">
                <MapPinned size={14} />
                <span>开场状态</span>
              </div>
              <StoryMapTextarea
                collaborationPath="opening_state"
                collaborationUnit="artifact"
                label="故事开始时，人物和局面处于什么压力之下"
                value={artifact.opening_state}
                editable={editable}
                onChange={(opening_state) => patch({ opening_state })}
              />
              <StoryMapTextarea
                collaborationPath="story_question"
                collaborationUnit="artifact"
                label="贯穿全文、最终需要回答的故事问题"
                value={artifact.story_question}
                editable={editable}
                onChange={(story_question) => patch({ story_question })}
                emphasized
              />
            </section>
          ) : null}

          {section === "anchor" ? (
            <div className="story-map-anchor-flow">
              {artifact.anchors.map((anchor, index) =>
                anchor.anchor_ref === selectedAnchorRef ? (
                  <section
                    key={anchor.anchor_ref}
                    className={`story-map-anchor-sheet${
                      selectedAnchorRef === anchor.anchor_ref
                        ? " is-active"
                        : ""
                    }`}
                    id={`story-map-${anchor.anchor_ref}`}
                    onFocus={() => setSelectedAnchorRef(anchor.anchor_ref)}
                    onMouseDown={() => setSelectedAnchorRef(anchor.anchor_ref)}
                  >
                    <header>
                      <div>
                        <span>{String(index + 1).padStart(2, "0")}</span>
                        <div>
                          <strong>故事锚点</strong>
                          <code>{anchor.anchor_ref}</code>
                        </div>
                      </div>
                      {editable ? (
                        <div
                          className="story-map-order-actions"
                          aria-label="调整锚点顺序"
                        >
                          <button
                            type="button"
                            title="上移"
                            aria-label={`上移锚点 ${index + 1}`}
                            disabled={!editable || index === 0}
                            onClick={() => moveAnchor(index, -1)}
                          >
                            <ArrowUp size={13} />
                          </button>
                          <button
                            type="button"
                            title="下移"
                            aria-label={`下移锚点 ${index + 1}`}
                            disabled={
                              !editable || index === artifact.anchors.length - 1
                            }
                            onClick={() => moveAnchor(index, 1)}
                          >
                            <ArrowDown size={13} />
                          </button>
                        </div>
                      ) : null}
                    </header>

                    <StoryMapTextarea
                      collaborationPath={`anchors.${index}.dramatic_job`}
                      collaborationUnit={anchor.anchor_ref}
                      label="戏剧任务"
                      value={anchor.dramatic_job}
                      editable={editable}
                      onChange={(dramatic_job) =>
                        patchAnchor(index, { dramatic_job })
                      }
                      emphasized
                    />
                    <div className="story-map-anchor-fields">
                      <StoryMapTextarea
                        collaborationPath={`anchors.${index}.pressure`}
                        collaborationUnit={anchor.anchor_ref}
                        label="压力如何升级"
                        value={anchor.pressure}
                        editable={editable}
                        onChange={(pressure) =>
                          patchAnchor(index, { pressure })
                        }
                      />
                      <StoryMapTextarea
                        collaborationPath={`anchors.${index}.choice_or_revelation`}
                        collaborationUnit={anchor.anchor_ref}
                        label="人物做出什么选择，或读者获得什么揭示"
                        value={anchor.choice_or_revelation}
                        editable={editable}
                        onChange={(choice_or_revelation) =>
                          patchAnchor(index, { choice_or_revelation })
                        }
                      />
                      <StoryMapTextarea
                        collaborationPath={`anchors.${index}.consequence_or_open_effect`}
                        collaborationUnit={anchor.anchor_ref}
                        label="造成什么后果，或留下什么开放效果"
                        value={anchor.consequence_or_open_effect}
                        editable={editable}
                        onChange={(consequence_or_open_effect) =>
                          patchAnchor(index, { consequence_or_open_effect })
                        }
                      />
                    </div>
                    <div className="story-map-promise-row">
                      <span>
                        <Link2 size={11} /> Promise 引用
                      </span>
                      <div>
                        {anchor.promise_refs.length > 0 ? (
                          anchor.promise_refs.map((promiseRef) => (
                            <code key={promiseRef}>{promiseRef}</code>
                          ))
                        ) : (
                          <em>当前锚点未绑定 Promise</em>
                        )}
                      </div>
                    </div>
                  </section>
                ) : null,
              )}
            </div>
          ) : null}

          {section === "ending" ? (
            <div className="story-map-ending-stack">
              <section className="story-map-boundary is-ending">
                <div className="story-map-boundary-label">
                  <Flag size={14} />
                  <span>收束条件</span>
                </div>
                <StoryMapTextarea
                  collaborationPath="ending_state"
                  collaborationUnit="artifact"
                  label="故事结束后，人物和局面发生了什么不可逆变化"
                  value={artifact.ending_state}
                  editable={editable}
                  onChange={(ending_state) => patch({ ending_state })}
                  emphasized
                />
              </section>

              <section className="story-map-open-questions">
                <header>
                  <div>
                    <CircleHelp size={13} />
                    <span>仍需追问</span>
                  </div>
                  <small>{artifact.open_questions.length} 条开放问题</small>
                </header>
                <div>
                  {artifact.open_questions.map((question, index) =>
                    editable ? (
                      <label key={index}>
                        <span>{String(index + 1).padStart(2, "0")}</span>
                        <textarea
                          data-collaboration-field-path={`open_questions.${index}`}
                          data-collaboration-unit="artifact"
                          value={question}
                          rows={2}
                          onChange={(event) =>
                            patchQuestion(index, event.target.value)
                          }
                        />
                        <button
                          type="button"
                          title="删除开放问题"
                          aria-label={`删除开放问题 ${index + 1}`}
                          onClick={() => removeQuestion(index)}
                        >
                          <Trash2 size={13} />
                        </button>
                      </label>
                    ) : (
                      <div className="story-map-question-row" key={index}>
                        <span>{String(index + 1).padStart(2, "0")}</span>
                        <p>{question}</p>
                      </div>
                    ),
                  )}
                </div>
                {editable ? (
                  <div className="story-map-question-composer">
                    <input
                      value={newQuestion}
                      placeholder="补充一个仍需在下游回答的问题"
                      onChange={(event) => setNewQuestion(event.target.value)}
                      onKeyDown={(event) => {
                        if (event.key !== "Enter") return
                        event.preventDefault()
                        addQuestion()
                      }}
                    />
                    <button
                      type="button"
                      disabled={!newQuestion.trim()}
                      onClick={addQuestion}
                    >
                      <Plus size={13} /> 添加
                    </button>
                  </div>
                ) : null}
              </section>
            </div>
          ) : null}
        </main>
      </div>

      <aside className="story-map-inspector" aria-label="故事地图检查器">
        <section>
          <span>结构概览</span>
          <dl>
            <div>
              <dt>故事锚点</dt>
              <dd>{diagnostics.anchorCount}</dd>
            </div>
            <div>
              <dt>Promise 引用</dt>
              <dd>{diagnostics.promiseRefs.length}</dd>
            </div>
            <div>
              <dt>开放问题</dt>
              <dd>{diagnostics.openQuestionCount}</dd>
            </div>
          </dl>
        </section>
        <section>
          <span>Promise 覆盖观察</span>
          {diagnostics.promiseRefs.length > 0 ? (
            <div className="story-map-inspector-refs">
              {diagnostics.promiseRefs.map((promiseRef) => (
                <code key={promiseRef}>{promiseRef}</code>
              ))}
            </div>
          ) : (
            <p>当前故事地图尚未关联读者承诺。</p>
          )}
          {diagnostics.anchorsWithoutPromise.length > 0 ? (
            <small className="is-warning">
              {diagnostics.anchorsWithoutPromise.length} 个锚点未绑定
              Promise；这是作者提示，不阻断定稿。
            </small>
          ) : null}
          <small>
            当前没有正式 Promise
            registry；此处只统计引用分布，不宣称上游承诺已核验。
          </small>
        </section>
        <section>
          <span>版本来源</span>
          <code title={artifactRef}>{shortRef(artifactRef)}</code>
          <small>{revisionLabel}</small>
          <small>
            {editable ? "编辑会保存为当前决策草稿。" : "当前为稳定阅读视图。"}
          </small>
        </section>
      </aside>
    </div>
  )
}

function StoryMapTextarea({
  collaborationPath,
  collaborationUnit,
  label,
  value,
  editable,
  emphasized = false,
  onChange,
}: {
  collaborationPath: string
  collaborationUnit: string
  label: string
  value: string
  editable: boolean
  emphasized?: boolean
  onChange: (value: string) => void
}) {
  if (!editable) {
    return (
      <div
        className={`story-map-field artifact-readable-field${
          emphasized ? " is-emphasized" : ""
        }`}
      >
        <span>{label}</span>
        <p className="artifact-readable-value">{value}</p>
      </div>
    )
  }
  return (
    <label className={`story-map-field${emphasized ? " is-emphasized" : ""}`}>
      <span>{label}</span>
      <textarea
        data-collaboration-field-path={collaborationPath}
        data-collaboration-unit={collaborationUnit}
        rows={3}
        value={value}
        readOnly={!editable}
        onChange={(event) => onChange(event.target.value)}
      />
    </label>
  )
}

function shortRef(value: string) {
  return value.length > 32 ? `${value.slice(0, 18)}…${value.slice(-9)}` : value
}
