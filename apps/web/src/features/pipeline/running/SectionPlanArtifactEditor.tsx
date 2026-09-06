import { useEffect, useMemo, useState } from "react"
import {
  ArrowDown,
  ArrowRight,
  ArrowUp,
  BookOpenText,
  CircleDot,
  Flag,
  Gauge,
  Link2,
  ListOrdered,
  Route,
  Target,
  UserRound,
} from "lucide-react"
import {
  formatSectionPlanBudget,
  reorderSectionPlanUnits,
  sectionPlanDiagnostics,
  type SectionPlanDraft,
  type SectionPlanReferenceContext,
  type SectionPlanUnitDraft,
} from "../lib/phase32SectionPlan"
import {
  SectionPlanContextCell,
  SectionPlanTextField,
  shortSectionPlanRef,
} from "./SectionPlanEditorFields"

type Props = {
  artifact: SectionPlanDraft
  artifactRef: string
  editable: boolean
  onChange: (value: Record<string, unknown>) => void
  referenceContext: SectionPlanReferenceContext
  revisionLabel: string
}

type SectionPlanSection = "engine" | "load" | "handoff"

export function SectionPlanArtifactEditor({
  artifact,
  artifactRef,
  editable,
  onChange,
  referenceContext,
  revisionLabel,
}: Props) {
  const [selectedUnitRef, setSelectedUnitRef] = useState(
    artifact.units[0]?.unit_ref ?? "",
  )
  const [section, setSection] = useState<SectionPlanSection>("engine")
  const diagnostics = useMemo(
    () => sectionPlanDiagnostics(artifact),
    [artifact],
  )
  const selectedIndex = Math.max(
    0,
    artifact.units.findIndex((unit) => unit.unit_ref === selectedUnitRef),
  )
  const selectedUnit = artifact.units[selectedIndex]
  const previousUnit = artifact.units[selectedIndex - 1]
  const nextUnit = artifact.units[selectedIndex + 1]

  useEffect(() => {
    if (artifact.units.some((unit) => unit.unit_ref === selectedUnitRef)) return
    setSelectedUnitRef(artifact.units[0]?.unit_ref ?? "")
  }, [artifact.units, selectedUnitRef])

  useEffect(() => setSection("engine"), [selectedUnitRef])

  const patch = (units: SectionPlanUnitDraft[]) => onChange({ units })
  const patchUnit = (value: Partial<SectionPlanUnitDraft>) => {
    patch(
      artifact.units.map((unit, index) =>
        index === selectedIndex ? { ...unit, ...value } : unit,
      ),
    )
  }
  const moveUnit = (offset: -1 | 1) => {
    patch(reorderSectionPlanUnits(artifact.units, selectedIndex, offset))
  }

  return (
    <div
      className={`section-plan-workbench artifact-mode-surface ${
        editable ? "is-editing" : "is-viewing"
      }`}
    >
      <nav className="section-plan-rail" aria-label="章节与段落单元导航">
        <header>
          <div>
            <ListOrdered size={13} />
            <span>正文单元</span>
          </div>
          <strong>{artifact.units.length}</strong>
        </header>
        <div className="section-plan-rail-list">
          {artifact.units.map((unit, index) => (
            <button
              aria-current={
                selectedUnitRef === unit.unit_ref ? "step" : undefined
              }
              className={selectedUnitRef === unit.unit_ref ? "is-active" : ""}
              key={unit.unit_ref}
              onClick={() => setSelectedUnitRef(unit.unit_ref)}
              type="button"
            >
              <span>{String(index + 1).padStart(2, "0")}</span>
              <span>
                <strong>{unit.title}</strong>
                <small>{unit.dramatic_job}</small>
                <i>
                  {referenceContext.cast[unit.pov_subject_ref]?.label ??
                    unit.pov_subject_ref}
                  <b>
                    {formatSectionPlanBudget(unit.soft_character_budget)} 字
                  </b>
                </i>
              </span>
              <em aria-hidden="true" />
            </button>
          ))}
        </div>
        <footer>
          <Link2 size={12} />
          <span>单元身份随候选冻结，正文按这里的顺序生成</span>
        </footer>
      </nav>

      <div className="section-plan-scroll">
        <div className="section-plan-mobile-nav" aria-label="正文单元快捷导航">
          {artifact.units.map((unit, index) => (
            <button
              className={selectedUnitRef === unit.unit_ref ? "is-active" : ""}
              key={unit.unit_ref}
              onClick={() => setSelectedUnitRef(unit.unit_ref)}
              type="button"
            >
              {String(index + 1).padStart(2, "0")}
            </button>
          ))}
        </div>

        <main className="section-plan-canvas">
          <header className="section-plan-heading">
            <div>
              <span>SHORT / MEDIUM NOVEL · SECTION PLAN</span>
              <h1>正文单元施工排程</h1>
            </div>
            <p>把故事地图落成连续的写作任务，并为下一单元留下明确入口。</p>
          </header>

          {selectedUnit ? (
            <section className="section-plan-sheet">
              <header className="section-plan-sheet-header">
                <div className="section-plan-sheet-identity">
                  <span>{String(selectedUnit.ordinal).padStart(2, "0")}</span>
                  <div>
                    {editable ? (
                      <label>
                        <span>单元标题</span>
                        <input
                          aria-label="单元标题"
                          onChange={(event) =>
                            patchUnit({ title: event.target.value })
                          }
                          value={selectedUnit.title}
                        />
                      </label>
                    ) : (
                      <div>
                        <span>单元标题</span>
                        <strong>{selectedUnit.title}</strong>
                      </div>
                    )}
                    <code>{selectedUnit.unit_ref}</code>
                  </div>
                </div>
                <div className="section-plan-sheet-controls">
                  {editable ? (
                    <label className="section-plan-budget-editor">
                      <Gauge size={12} />
                      <span>软字数</span>
                      <input
                        aria-label="单元软字数"
                        max={100_000}
                        min={100}
                        onChange={(event) =>
                          patchUnit({
                            soft_character_budget: Number(event.target.value),
                          })
                        }
                        step={100}
                        type="number"
                        value={selectedUnit.soft_character_budget}
                      />
                    </label>
                  ) : (
                    <div className="section-plan-budget-readout">
                      <Gauge size={12} />
                      <span>软字数</span>
                      <strong>
                        {formatSectionPlanBudget(
                          selectedUnit.soft_character_budget,
                        )}
                      </strong>
                    </div>
                  )}
                  {editable ? (
                    <div aria-label="调整正文单元顺序">
                      <IconButton
                        disabled={selectedIndex === 0}
                        label={`上移单元 ${selectedUnit.ordinal}`}
                        onClick={() => moveUnit(-1)}
                      >
                        <ArrowUp size={13} />
                      </IconButton>
                      <IconButton
                        disabled={selectedIndex === artifact.units.length - 1}
                        label={`下移单元 ${selectedUnit.ordinal}`}
                        onClick={() => moveUnit(1)}
                      >
                        <ArrowDown size={13} />
                      </IconButton>
                    </div>
                  ) : null}
                </div>
              </header>

              <div className="section-plan-scope-strip">
                <div>
                  <span>
                    <UserRound size={11} /> POV
                  </span>
                  {editable ? (
                    <select
                      aria-label="单元 POV"
                      onChange={(event) =>
                        patchUnit({ pov_subject_ref: event.target.value })
                      }
                      value={selectedUnit.pov_subject_ref}
                    >
                      {Object.values(referenceContext.cast).map((character) => (
                        <option key={character.ref} value={character.ref}>
                          {character.label}
                        </option>
                      ))}
                    </select>
                  ) : (
                    <strong>
                      {referenceContext.cast[selectedUnit.pov_subject_ref]
                        ?.label ?? selectedUnit.pov_subject_ref}
                    </strong>
                  )}
                </div>
                <div>
                  <span>
                    <Link2 size={11} /> 读者承诺
                  </span>
                  <div className="section-plan-promise-list">
                    {selectedUnit.promise_refs.length > 0 ? (
                      selectedUnit.promise_refs.map((promiseRef) => (
                        <code key={promiseRef}>{promiseRef}</code>
                      ))
                    ) : (
                      <em>当前单元未绑定 Promise</em>
                    )}
                  </div>
                </div>
              </div>

              <nav className="artifact-section-tabs" aria-label="正文单元分区">
                <button
                  className={section === "engine" ? "is-active" : ""}
                  onClick={() => setSection("engine")}
                  type="button"
                >
                  戏剧任务
                </button>
                <button
                  className={section === "load" ? "is-active" : ""}
                  onClick={() => setSection("load")}
                  type="button"
                >
                  场景负载
                </button>
                <button
                  className={section === "handoff" ? "is-active" : ""}
                  onClick={() => setSection("handoff")}
                  type="button"
                >
                  状态交接
                </button>
              </nav>

              {section === "engine" ? (
                <div className="section-plan-engine">
                  <div className="section-plan-continuity-flow">
                    <SectionPlanContextCell
                      eyebrow={previousUnit ? "上一单元交来" : "故事开场入口"}
                      icon={<Route size={11} />}
                    >
                      {previousUnit?.handoff ??
                        "承接已确认故事地图的开场压力。"}
                    </SectionPlanContextCell>
                    <ArrowRight aria-hidden="true" size={14} />
                    <SectionPlanContextCell
                      eyebrow="当前正文任务"
                      icon={<Target size={11} />}
                      tone="active"
                    >
                      {selectedUnit.dramatic_job}
                    </SectionPlanContextCell>
                    <ArrowRight aria-hidden="true" size={14} />
                    <SectionPlanContextCell
                      eyebrow={nextUnit ? "交给下一单元" : "交给全文收束"}
                      icon={<Flag size={11} />}
                    >
                      {selectedUnit.handoff}
                    </SectionPlanContextCell>
                  </div>
                  <SectionPlanTextField
                    collaborationPath={`units.${selectedIndex}.dramatic_job`}
                    collaborationUnit={selectedUnit.unit_ref}
                    editable={editable}
                    emphasized
                    icon={<Target size={12} />}
                    label="本单元必须完成的戏剧任务"
                    onChange={(dramatic_job) => patchUnit({ dramatic_job })}
                    rows={5}
                    value={selectedUnit.dramatic_job}
                  />
                </div>
              ) : null}

              {section === "load" ? (
                <div className="section-plan-load">
                  <header>
                    <div>
                      <BookOpenText size={13} />
                      <span>场景负载说明</span>
                    </div>
                    <small>不是固定场景配额</small>
                  </header>
                  <SectionPlanTextField
                    collaborationPath={`units.${selectedIndex}.scene_load`}
                    collaborationUnit={selectedUnit.unit_ref}
                    editable={editable}
                    icon={<CircleDot size={12} />}
                    label="为完成当前任务，需要哪些场景、转换或叙述负载"
                    onChange={(scene_load) => patchUnit({ scene_load })}
                    rows={8}
                    value={selectedUnit.scene_load}
                  />
                  <div className="section-plan-load-ledger">
                    <div>
                      <span>叙事视角</span>
                      <strong>
                        {referenceContext.cast[selectedUnit.pov_subject_ref]
                          ?.label ?? selectedUnit.pov_subject_ref}
                      </strong>
                    </div>
                    <div>
                      <span>软字数</span>
                      <strong>
                        {formatSectionPlanBudget(
                          selectedUnit.soft_character_budget,
                        )}{" "}
                        字
                      </strong>
                    </div>
                    <div>
                      <span>承诺引用</span>
                      <strong>{selectedUnit.promise_refs.length}</strong>
                    </div>
                  </div>
                </div>
              ) : null}

              {section === "handoff" ? (
                <div className="section-plan-handoff">
                  <SectionPlanTextField
                    collaborationPath={`units.${selectedIndex}.handoff`}
                    collaborationUnit={selectedUnit.unit_ref}
                    editable={editable}
                    emphasized
                    icon={<Flag size={12} />}
                    label="本单元结束时，交给下一单元的状态与入口"
                    onChange={(handoff) => patchUnit({ handoff })}
                    rows={6}
                    value={selectedUnit.handoff}
                  />
                  <aside>
                    <span>{nextUnit ? "下一单元接力" : "全文收束"}</span>
                    <strong>{nextUnit?.title ?? "进入正文最终收束"}</strong>
                    <p>
                      {nextUnit?.dramatic_job ??
                        "当前 handoff 将作为正文末段的收束入口。"}
                    </p>
                  </aside>
                </div>
              ) : null}
            </section>
          ) : null}
        </main>
      </div>

      <aside className="section-plan-inspector" aria-label="章节计划检查器">
        <section>
          <span>施工概览</span>
          <dl>
            <div>
              <dt>正文单元</dt>
              <dd>{diagnostics.unitCount}</dd>
            </div>
            <div>
              <dt>软字数</dt>
              <dd>
                {formatSectionPlanBudget(diagnostics.totalCharacterBudget)}
              </dd>
            </div>
            <div>
              <dt>POV</dt>
              <dd>{diagnostics.uniquePovCount}</dd>
            </div>
          </dl>
        </section>
        <section>
          <span>Promise 覆盖</span>
          {diagnostics.promiseCoverage.length > 0 ? (
            <div className="section-plan-inspector-coverage">
              {diagnostics.promiseCoverage.map((item) => (
                <div key={item.promiseRef}>
                  <code>{item.promiseRef}</code>
                  <small>{item.unitRefs.length} 个单元</small>
                </div>
              ))}
            </div>
          ) : (
            <p>当前计划尚未带入 Story Map Promise。</p>
          )}
          {diagnostics.unitsWithoutPromise.length > 0 ? (
            <small className="is-warning">
              {diagnostics.unitsWithoutPromise.length} 个单元未绑定
              Promise；这是作者提示，不阻断定稿。
            </small>
          ) : null}
        </section>
        <section>
          <span>当前引用来源</span>
          {selectedUnit?.promise_refs.length ? (
            selectedUnit.promise_refs.map((promiseRef) => (
              <div className="section-plan-origin" key={promiseRef}>
                <code>{promiseRef}</code>
                <small>
                  {referenceContext.promises[promiseRef]?.labels.join(" · ") ||
                    "来自已确认故事地图"}
                </small>
              </div>
            ))
          ) : (
            <p>当前单元没有 Promise 来源。</p>
          )}
        </section>
        <section>
          <span>版本来源</span>
          <code title={artifactRef}>{shortSectionPlanRef(artifactRef)}</code>
          <small>{revisionLabel}</small>
          <small>
            {editable
              ? "只编辑当前单元，草稿自动保存。"
              : "当前为稳定阅读视图。"}
          </small>
        </section>
      </aside>
    </div>
  )
}

function IconButton({
  children,
  disabled,
  label,
  onClick,
}: {
  children: import("react").ReactNode
  disabled: boolean
  label: string
  onClick: () => void
}) {
  return (
    <button
      aria-label={label}
      disabled={disabled}
      onClick={onClick}
      type="button"
    >
      {children}
    </button>
  )
}
