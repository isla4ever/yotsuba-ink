import { useEffect, useMemo, useState } from "react"
import {
  ArrowDown,
  ArrowUp,
  BookOpenText,
  Braces,
  CircleHelp,
  Flag,
  Link2,
  Network,
  Trash2,
} from "lucide-react"
import {
  bookArchitectureDiagnostics,
  reorderBookParts,
  type BookArchitectureDraft,
  type BookPartDraft,
} from "../lib/phase32BookArchitecture"
import {
  ArchitectureTextarea,
  InlineComposer,
  ReferenceLedger,
  shortArtifactRef,
} from "./BookArchitectureEditorFields"

type Props = {
  artifact: BookArchitectureDraft
  artifactRef: string
  editable: boolean
  revisionLabel: string
  onChange: (value: Record<string, unknown>) => void
}

type ArchitectureSection = "root" | "part"

export function BookArchitectureArtifactEditor({
  artifact,
  artifactRef,
  editable,
  revisionLabel,
  onChange,
}: Props) {
  const [selectedPartRef, setSelectedPartRef] = useState(
    artifact.parts[0]?.part_ref ?? "",
  )
  const [section, setSection] = useState<ArchitectureSection>("part")
  const [newEndingCondition, setNewEndingCondition] = useState("")
  const [newObligation, setNewObligation] = useState("")
  const diagnostics = useMemo(
    () => bookArchitectureDiagnostics(artifact),
    [artifact],
  )
  const selectedIndex = Math.max(
    0,
    artifact.parts.findIndex((part) => part.part_ref === selectedPartRef),
  )
  const selectedPart = artifact.parts[selectedIndex]

  useEffect(() => {
    if (artifact.parts.some((part) => part.part_ref === selectedPartRef)) return
    setSelectedPartRef(artifact.parts[0]?.part_ref ?? "")
  }, [artifact.parts, selectedPartRef])

  const patch = (value: Partial<BookArchitectureDraft>) =>
    onChange({ ...artifact, ...value })

  const patchPart = (index: number, value: Partial<BookPartDraft>) => {
    patch({
      parts: artifact.parts.map((part, partIndex) =>
        partIndex === index ? { ...part, ...value } : part,
      ),
    })
  }

  const movePart = (index: number, offset: -1 | 1) => {
    patch({ parts: reorderBookParts(artifact.parts, index, offset) })
  }

  const patchEndingCondition = (index: number, value: string) => {
    patch({
      ending_conditions: artifact.ending_conditions.map(
        (condition, conditionIndex) =>
          conditionIndex === index ? value : condition,
      ),
    })
  }

  const removeEndingCondition = (index: number) => {
    if (artifact.ending_conditions.length <= 1) return
    patch({
      ending_conditions: artifact.ending_conditions.filter(
        (_, conditionIndex) => conditionIndex !== index,
      ),
    })
  }

  const addEndingCondition = () => {
    const condition = newEndingCondition.trim()
    if (!condition || artifact.ending_conditions.length >= 32) return
    patch({ ending_conditions: [...artifact.ending_conditions, condition] })
    setNewEndingCondition("")
  }

  const patchObligation = (index: number, value: string) => {
    if (!selectedPart) return
    patchPart(selectedIndex, {
      unresolved_obligations: selectedPart.unresolved_obligations.map(
        (obligation, obligationIndex) =>
          obligationIndex === index ? value : obligation,
      ),
    })
  }

  const removeObligation = (index: number) => {
    if (!selectedPart) return
    patchPart(selectedIndex, {
      unresolved_obligations: selectedPart.unresolved_obligations.filter(
        (_, obligationIndex) => obligationIndex !== index,
      ),
    })
  }

  const addObligation = () => {
    const obligation = newObligation.trim()
    if (
      !selectedPart ||
      !obligation ||
      selectedPart.unresolved_obligations.length >= 32
    )
      return
    patchPart(selectedIndex, {
      unresolved_obligations: [
        ...selectedPart.unresolved_obligations,
        obligation,
      ],
    })
    setNewObligation("")
  }

  return (
    <div
      className={`book-architecture-workbench artifact-mode-surface ${
        editable ? "is-editing" : "is-viewing"
      }`}
    >
      <nav className="book-architecture-part-rail" aria-label="全书 Part 导航">
        <header>
          <div>
            <BookOpenText size={13} />
            <span>全书分部</span>
          </div>
          <strong>{artifact.parts.length}</strong>
        </header>
        <div className="book-architecture-part-list">
          {artifact.parts.map((part, index) => (
            <button
              type="button"
              key={part.part_ref}
              className={selectedPartRef === part.part_ref ? "is-active" : ""}
              aria-current={
                selectedPartRef === part.part_ref ? "step" : undefined
              }
              onClick={() => {
                setSelectedPartRef(part.part_ref)
                setSection("part")
                setNewObligation("")
              }}
            >
              <span>{String(index + 1).padStart(2, "0")}</span>
              <span>
                <strong>PART {String(index + 1).padStart(2, "0")}</strong>
                <small>{part.dramatic_question}</small>
              </span>
              <i aria-hidden="true" />
            </button>
          ))}
        </div>
        <footer>
          <Network size={12} />
          <span>Part 顺序随聚合根一次提交</span>
        </footer>
      </nav>

      <div className="book-architecture-scroll">
        <div
          className="book-architecture-mobile-parts"
          aria-label="全书 Part 快捷导航"
        >
          {artifact.parts.map((part, index) => (
            <button
              type="button"
              key={part.part_ref}
              className={selectedPartRef === part.part_ref ? "is-active" : ""}
              onClick={() => {
                setSelectedPartRef(part.part_ref)
                setSection("part")
              }}
            >
              P{String(index + 1).padStart(2, "0")}
            </button>
          ))}
        </div>

        <main className="book-architecture-canvas">
          <header className="book-architecture-heading">
            <div>
              <span>LONG NOVEL · BOOK ARCHITECTURE</span>
              <h1>全书承诺与 Part 契约</h1>
            </div>
            <p>先校准整本兑现，再检查每一分部如何进入、转折并交棒。</p>
          </header>

          <nav className="artifact-section-tabs" aria-label="全书架构分区">
            <button
              className={section === "root" ? "is-active" : ""}
              onClick={() => setSection("root")}
              type="button"
            >
              全书根契约
              <span>{artifact.ending_conditions.length}</span>
            </button>
            <button
              className={section === "part" ? "is-active" : ""}
              onClick={() => setSection("part")}
              type="button"
            >
              当前 Part
              <span>{String(selectedIndex + 1).padStart(2, "0")}</span>
            </button>
          </nav>

          {section === "root" ? (
            <section className="book-architecture-root">
              <div className="book-architecture-section-label">
                <BookOpenText size={14} />
                <span>全书根契约</span>
              </div>
              <ArchitectureTextarea
                collaborationPath="book_promise"
                collaborationUnit="artifact"
                label="这部长篇持续向读者承诺什么"
                value={artifact.book_promise}
                editable={editable}
                emphasized
                rows={4}
                onChange={(book_promise) => patch({ book_promise })}
              />
              <div className="book-architecture-ending-ledger">
                <header>
                  <div>
                    <Flag size={13} />
                    <span>终局成立条件</span>
                  </div>
                  <small>{artifact.ending_conditions.length} 条</small>
                </header>
                <div>
                  {artifact.ending_conditions.map((condition, index) =>
                    editable ? (
                      <label key={index}>
                        <span>{String(index + 1).padStart(2, "0")}</span>
                        <textarea
                          data-collaboration-field-path={`ending_conditions.${index}`}
                          data-collaboration-unit="artifact"
                          rows={2}
                          value={condition}
                          onChange={(event) =>
                            patchEndingCondition(index, event.target.value)
                          }
                        />
                        <button
                          type="button"
                          title="删除终局条件"
                          aria-label={`删除终局条件 ${index + 1}`}
                          disabled={artifact.ending_conditions.length <= 1}
                          onClick={() => removeEndingCondition(index)}
                        >
                          <Trash2 size={13} />
                        </button>
                      </label>
                    ) : (
                      <div className="book-architecture-ledger-row" key={index}>
                        <span>{String(index + 1).padStart(2, "0")}</span>
                        <p>{condition}</p>
                      </div>
                    ),
                  )}
                </div>
                {editable ? (
                  <InlineComposer
                    value={newEndingCondition}
                    placeholder="补充一个全书最终必须兑现的条件"
                    disabled={artifact.ending_conditions.length >= 32}
                    onChange={setNewEndingCondition}
                    onSubmit={addEndingCondition}
                  />
                ) : null}
              </div>
            </section>
          ) : null}

          {section === "part" && selectedPart ? (
            <section className="book-architecture-part-sheet">
              <header>
                <div>
                  <span>{String(selectedIndex + 1).padStart(2, "0")}</span>
                  <div>
                    <strong>分部契约</strong>
                    <code>{selectedPart.part_ref}</code>
                  </div>
                </div>
                {editable ? (
                  <div
                    className="book-architecture-order-actions"
                    aria-label="调整 Part 顺序"
                  >
                    <button
                      type="button"
                      title="上移"
                      aria-label={`上移 Part ${selectedIndex + 1}`}
                      disabled={!editable || selectedIndex === 0}
                      onClick={() => movePart(selectedIndex, -1)}
                    >
                      <ArrowUp size={13} />
                    </button>
                    <button
                      type="button"
                      title="下移"
                      aria-label={`下移 Part ${selectedIndex + 1}`}
                      disabled={
                        !editable || selectedIndex === artifact.parts.length - 1
                      }
                      onClick={() => movePart(selectedIndex, 1)}
                    >
                      <ArrowDown size={13} />
                    </button>
                  </div>
                ) : null}
              </header>

              <ArchitectureTextarea
                collaborationPath={`parts.${selectedIndex}.dramatic_question`}
                collaborationUnit={selectedPart.part_ref}
                label="本 Part 要持续回答的戏剧问题"
                value={selectedPart.dramatic_question}
                editable={editable}
                emphasized
                rows={3}
                onChange={(dramatic_question) =>
                  patchPart(selectedIndex, { dramatic_question })
                }
              />
              <div className="book-architecture-state-handoff">
                <ArchitectureTextarea
                  collaborationPath={`parts.${selectedIndex}.entry_state`}
                  collaborationUnit={selectedPart.part_ref}
                  label="进入状态"
                  value={selectedPart.entry_state}
                  editable={editable}
                  rows={4}
                  onChange={(entry_state) =>
                    patchPart(selectedIndex, { entry_state })
                  }
                />
                <div
                  className="book-architecture-handoff-mark"
                  aria-hidden="true"
                >
                  <span />
                  <Network size={15} />
                  <span />
                </div>
                <ArchitectureTextarea
                  collaborationPath={`parts.${selectedIndex}.exit_state`}
                  collaborationUnit={selectedPart.part_ref}
                  label="退出状态"
                  value={selectedPart.exit_state}
                  editable={editable}
                  rows={4}
                  onChange={(exit_state) =>
                    patchPart(selectedIndex, { exit_state })
                  }
                />
              </div>

              <div className="book-architecture-ref-ledgers">
                <ReferenceLedger
                  icon={<Link2 size={12} />}
                  label="Promise 引用"
                  refs={selectedPart.promise_refs}
                />
                <ReferenceLedger
                  icon={<Braces size={12} />}
                  label="转折引用"
                  refs={selectedPart.turning_point_refs}
                />
              </div>

              <div className="book-architecture-obligations">
                <header>
                  <div>
                    <CircleHelp size={13} />
                    <span>离开本 Part 时仍未解决</span>
                  </div>
                  <small>{selectedPart.unresolved_obligations.length} 条</small>
                </header>
                {selectedPart.unresolved_obligations.length > 0 ? (
                  <div>
                    {selectedPart.unresolved_obligations.map(
                      (obligation, index) =>
                        editable ? (
                          <label key={index}>
                            <span>{String(index + 1).padStart(2, "0")}</span>
                            <textarea
                              data-collaboration-field-path={`parts.${selectedIndex}.unresolved_obligations.${index}`}
                              data-collaboration-unit={selectedPart.part_ref}
                              rows={2}
                              value={obligation}
                              onChange={(event) =>
                                patchObligation(index, event.target.value)
                              }
                            />
                            <button
                              type="button"
                              title="删除未决责任"
                              aria-label={`删除未决责任 ${index + 1}`}
                              onClick={() => removeObligation(index)}
                            >
                              <Trash2 size={13} />
                            </button>
                          </label>
                        ) : (
                          <div
                            className="book-architecture-ledger-row"
                            key={index}
                          >
                            <span>{String(index + 1).padStart(2, "0")}</span>
                            <p>{obligation}</p>
                          </div>
                        ),
                    )}
                  </div>
                ) : (
                  <p>本 Part 当前没有带往下游的未决责任。</p>
                )}
                {editable ? (
                  <InlineComposer
                    value={newObligation}
                    placeholder="补充一个需要后续 Part 继续处理的责任"
                    disabled={selectedPart.unresolved_obligations.length >= 32}
                    onChange={setNewObligation}
                    onSubmit={addObligation}
                  />
                ) : null}
              </div>
            </section>
          ) : null}
        </main>
      </div>

      <aside
        className="book-architecture-inspector"
        aria-label="全书架构检查器"
      >
        <section>
          <span>聚合概览</span>
          <dl>
            <div>
              <dt>Part</dt>
              <dd>{diagnostics.partCount}</dd>
            </div>
            <div>
              <dt>终局条件</dt>
              <dd>{diagnostics.endingConditionCount}</dd>
            </div>
            <div>
              <dt>转折引用</dt>
              <dd>{diagnostics.turningPointCount}</dd>
            </div>
            <div>
              <dt>未决责任</dt>
              <dd>{diagnostics.unresolvedObligationCount}</dd>
            </div>
          </dl>
        </section>
        <section>
          <span>Promise 生命周期观察</span>
          <div className="book-architecture-lifecycle">
            {diagnostics.promiseLifecycle.map((item) => (
              <div key={item.promiseRef}>
                <code>{item.promiseRef}</code>
                <small>
                  {item.partRefs
                    .map(
                      (partRef) =>
                        `P${String(
                          artifact.parts.findIndex(
                            (part) => part.part_ref === partRef,
                          ) + 1,
                        ).padStart(2, "0")}`,
                    )
                    .join(" · ")}
                </small>
              </div>
            ))}
          </div>
          <small>
            此处只观察当前全书架构的承诺引用分布；没有正式承诺登记时不宣称已经核验。
          </small>
        </section>
        <section>
          <span>编辑边界</span>
          <p>可编辑全书与 Part 内容并重排现有 Part；稳定引用保持只读。</p>
          <small>新增或删除 Part 需要由服务端分配稳定标识。</small>
        </section>
        <section>
          <span>版本来源</span>
          <code title={artifactRef}>{shortArtifactRef(artifactRef)}</code>
          <small>{revisionLabel}</small>
          <small>
            {editable
              ? "全部 Part 随当前决策草稿一次保存。"
              : "当前为稳定阅读视图。"}
          </small>
        </section>
      </aside>
    </div>
  )
}
