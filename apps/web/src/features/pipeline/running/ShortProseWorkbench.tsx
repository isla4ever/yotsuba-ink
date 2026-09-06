import { useEffect, useMemo, useState } from "react"
import {
  ArrowRight,
  BadgeCheck,
  BookOpenText,
  CircleDashed,
  FileText,
  Gauge,
  Link2,
  LockKeyhole,
  Route,
  Target,
  UserRound,
} from "lucide-react"
import {
  formatShortProseCharacters,
  relatedShortProseAnchors,
  shortProseDiagnostics,
  shortProseParagraphs,
  shortProseUnitLabel,
  type ShortProseDraft,
  type ShortProseReferenceContext,
  type ShortProseUnitKind,
} from "../lib/phase32ShortProse"

type Props = {
  activeUnitRef: string
  artifact: ShortProseDraft | null
  artifactRef: string
  committedArtifactRefs: Record<string, string>
  editable: boolean
  expectedUnitKind: ShortProseUnitKind
  onChange: (value: Record<string, unknown>) => void
  onSelectUnit: (unitRef: string) => void
  orderedUnitRefs: string[]
  referenceContext: ShortProseReferenceContext
  revisionLabel: string
  selectedUnitRef: string
}

type InspectorSection = "plan" | "continuity"

export function ShortProseWorkbench({
  activeUnitRef,
  artifact,
  artifactRef,
  committedArtifactRefs,
  editable,
  expectedUnitKind,
  onChange,
  onSelectUnit,
  orderedUnitRefs,
  referenceContext,
  revisionLabel,
  selectedUnitRef,
}: Props) {
  const [inspectorSection, setInspectorSection] =
    useState<InspectorSection>("plan")
  const unitByRef = useMemo(
    () =>
      Object.fromEntries(
        referenceContext.units.map((unit) => [unit.unitRef, unit]),
      ),
    [referenceContext.units],
  )
  const selectedIndex = Math.max(0, orderedUnitRefs.indexOf(selectedUnitRef))
  const selectedUnit = unitByRef[selectedUnitRef]
  const previousUnit = unitByRef[orderedUnitRefs[selectedIndex - 1]]
  const nextUnit = unitByRef[orderedUnitRefs[selectedIndex + 1]]
  const pov = selectedUnit
    ? referenceContext.cast[selectedUnit.povSubjectRef]
    : undefined
  const anchors = relatedShortProseAnchors(
    selectedUnit,
    referenceContext.anchors,
  )
  const diagnostics = artifact
    ? shortProseDiagnostics(artifact, referenceContext)
    : null
  const paragraphs = artifact ? shortProseParagraphs(artifact.content) : []
  const previousCommittedRef = previousUnit
    ? committedArtifactRefs[previousUnit.unitRef]
    : ""

  useEffect(() => setInspectorSection("plan"), [selectedUnitRef])

  return (
    <div
      className={`short-prose-workbench artifact-mode-surface ${
        editable ? "is-editing" : "is-viewing"
      }`}
    >
      <nav className="short-prose-rail" aria-label="正文单元导航">
        <header>
          <div>
            <BookOpenText size={13} />
            <span>正文单元</span>
          </div>
          <strong>
            {Object.keys(committedArtifactRefs).length}/{orderedUnitRefs.length}
          </strong>
        </header>
        <div className="short-prose-rail-list">
          {orderedUnitRefs.map((unitRef, index) => {
            const unit = unitByRef[unitRef]
            const status = committedArtifactRefs[unitRef]
              ? "accepted"
              : unitRef === activeUnitRef
                ? "current"
                : "queued"
            return (
              <button
                aria-current={selectedUnitRef === unitRef ? "step" : undefined}
                className={`${
                  selectedUnitRef === unitRef ? "is-active" : ""
                } is-${status}`}
                key={unitRef}
                onClick={() => onSelectUnit(unitRef)}
                type="button"
              >
                <span>{String(index + 1).padStart(2, "0")}</span>
                <span>
                  <strong>{unit?.title || unitRef}</strong>
                  <small>
                    {unit
                      ? referenceContext.cast[unit.povSubjectRef]
                          ?.displayName || unit.povSubjectRef
                      : unitRef}
                  </small>
                  <i>{statusLabel(status)}</i>
                </span>
                <em aria-hidden="true" />
              </button>
            )
          })}
        </div>
        <footer>
          <LockKeyhole size={12} />
          <span>已接受正文保持不可变；只有当前单元可进入编辑态</span>
        </footer>
      </nav>

      <div className="short-prose-scroll">
        <div className="short-prose-mobile-nav" aria-label="正文单元快捷导航">
          {orderedUnitRefs.map((unitRef, index) => (
            <button
              className={selectedUnitRef === unitRef ? "is-active" : ""}
              key={unitRef}
              onClick={() => onSelectUnit(unitRef)}
              type="button"
            >
              {String(index + 1).padStart(2, "0")}
            </button>
          ))}
        </div>

        <main className="short-prose-canvas">
          <header className="short-prose-heading">
            <div>
              <span>SHORT / MEDIUM NOVEL · MANUSCRIPT</span>
              <h1>正文写作台</h1>
            </div>
            <p>按冻结单元顺序写作；阅读态优先，编辑只作用于当前候选正文。</p>
          </header>

          <article className="short-prose-sheet">
            <header className="short-prose-sheet-header">
              <div>
                <span>{String(selectedIndex + 1).padStart(2, "0")}</span>
                <div>
                  <small>{shortProseUnitLabel(expectedUnitKind)}</small>
                  <strong>{selectedUnit?.title || "等待正文单元"}</strong>
                  <code>{selectedUnitRef}</code>
                </div>
              </div>
              <div className="short-prose-sheet-meta">
                <span>{revisionLabel}</span>
                <span>
                  {diagnostics
                    ? `${formatShortProseCharacters(diagnostics.characterCount)} 字`
                    : "尚未生成"}
                </span>
              </div>
            </header>

            {artifact ? (
              editable ? (
                <label className="short-prose-editor">
                  <span>当前正文</span>
                  <textarea
                    aria-label="当前正文"
                    autoFocus
                    data-collaboration-field-path="content"
                    data-collaboration-unit={selectedUnitRef}
                    onChange={(event) =>
                      onChange({ ...artifact, content: event.target.value })
                    }
                    spellCheck={false}
                    value={artifact.content}
                  />
                </label>
              ) : (
                <div className="short-prose-manuscript page-in">
                  {paragraphs.map((paragraph, index) => (
                    <p key={`${index}-${paragraph.slice(0, 18)}`}>
                      {paragraph}
                    </p>
                  ))}
                </div>
              )
            ) : (
              <div className="short-prose-sheet-empty">
                <CircleDashed size={20} />
                <strong>该单元尚未进入正文生成</strong>
                <p>前序单元确认后，系统会使用其有限交接继续当前计划。</p>
              </div>
            )}

            <footer className="short-prose-sheet-footer">
              <span>
                <FileText size={11} />
                {diagnostics?.paragraphCount ?? 0} 个自然段
              </span>
              <code>{shortArtifactRef(artifactRef)}</code>
            </footer>
          </article>
        </main>
      </div>

      <aside className="short-prose-inspector">
        <header>
          <div>
            <Route size={13} />
            <strong>单元上下文</strong>
          </div>
          <div className="short-prose-inspector-tabs">
            <button
              aria-pressed={inspectorSection === "plan"}
              className={inspectorSection === "plan" ? "is-active" : ""}
              onClick={() => setInspectorSection("plan")}
              type="button"
            >
              计划
            </button>
            <button
              aria-pressed={inspectorSection === "continuity"}
              className={inspectorSection === "continuity" ? "is-active" : ""}
              onClick={() => setInspectorSection("continuity")}
              type="button"
            >
              交接
            </button>
          </div>
        </header>

        {inspectorSection === "plan" ? (
          <div className="short-prose-inspector-body page-in">
            <section className="short-prose-plan-lead">
              <span>
                <Target size={11} /> 戏剧任务
              </span>
              <p>{selectedUnit?.dramaticJob || "等待冻结单元计划"}</p>
            </section>
            <section>
              <span>
                <UserRound size={11} /> 当前 POV
              </span>
              <strong>
                {pov?.displayName || selectedUnit?.povSubjectRef || "-"}
              </strong>
              <small>{pov?.role || "人物职责来自已确认 Cast"}</small>
              {pov?.voice ? <p>声音：{pov.voice}</p> : null}
            </section>
            <section>
              <span>
                <Gauge size={11} /> 软字数
              </span>
              <div className="short-prose-budget">
                <strong>
                  {formatShortProseCharacters(diagnostics?.characterCount ?? 0)}
                </strong>
                <small>
                  /{" "}
                  {formatShortProseCharacters(
                    selectedUnit?.softCharacterBudget ?? 0,
                  )}{" "}
                  字
                </small>
              </div>
              <div className="short-prose-budget-track">
                <span
                  style={{
                    width: `${Math.min(100, Math.max(0, (diagnostics?.budgetRatio ?? 0) * 100))}%`,
                  }}
                />
              </div>
              <p>篇幅是写作参考，不因轻微偏差阻断确认。</p>
            </section>
            <section>
              <span>场景负载</span>
              <p>{selectedUnit?.sceneLoad || "当前单元尚无场景负载"}</p>
            </section>
            {anchors.length ? (
              <section>
                <span>Story Map 对应锚点</span>
                {anchors.map((anchor) => (
                  <div className="short-prose-anchor" key={anchor.anchorRef}>
                    <code>{anchor.anchorRef}</code>
                    <p>{anchor.dramaticJob}</p>
                  </div>
                ))}
              </section>
            ) : null}
          </div>
        ) : (
          <div className="short-prose-inspector-body page-in">
            <section>
              <span>
                <Link2 size={11} /> 上一单元交接
              </span>
              <p>
                {previousUnit?.handoff ||
                  "首个单元从 Brief 与 Story Map 的开场状态开始。"}
              </p>
              {previousUnit ? (
                <small className={previousCommittedRef ? "is-bound" : ""}>
                  {previousCommittedRef
                    ? "已绑定上一单元不可变版本"
                    : "等待上一单元确认"}
                </small>
              ) : null}
            </section>
            <section>
              <span>本单元交付</span>
              <p>{selectedUnit?.handoff || "完成单体故事的收束。"}</p>
            </section>
            <section className="short-prose-continuity-receipt">
              <span>
                <BadgeCheck size={11} /> 连续性回执
              </span>
              <dl>
                <div>
                  <dt>计划身份</dt>
                  <dd>{selectedUnit ? "已冻结" : "未就绪"}</dd>
                </div>
                <div>
                  <dt>相邻正文</dt>
                  <dd>
                    {!previousUnit || previousCommittedRef
                      ? "已绑定"
                      : "等待前序"}
                  </dd>
                </div>
                <div>
                  <dt>POV</dt>
                  <dd>{pov ? "已登记" : "待核验"}</dd>
                </div>
              </dl>
            </section>
            {nextUnit ? (
              <section className="short-prose-next-unit">
                <span>下一单元</span>
                <strong>{nextUnit.title}</strong>
                <p>{nextUnit.dramaticJob}</p>
                <ArrowRight size={12} />
              </section>
            ) : null}
          </div>
        )}
      </aside>
    </div>
  )
}

function statusLabel(status: "accepted" | "current" | "queued") {
  return {
    accepted: "已接受",
    current: "当前候选",
    queued: "等待前序",
  }[status]
}

function shortArtifactRef(value: string) {
  if (!value) return "NO ARTIFACT"
  return value.length > 34 ? `${value.slice(0, 22)}…${value.slice(-8)}` : value
}
