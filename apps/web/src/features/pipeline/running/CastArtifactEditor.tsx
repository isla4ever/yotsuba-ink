import {
  useEffect,
  useMemo,
  useState,
  type ComponentType,
  type CSSProperties,
} from "react"
import {
  ArrowRight,
  GitBranch,
  Network,
  Plus,
  ScanSearch,
  ShieldCheck,
  Trash2,
  UserRound,
  UsersRound,
} from "lucide-react"
import type { CreationRouteId } from "../contracts/run"
import { graphColorForSubject } from "../lib/characterGraph"
import {
  castDiagnostics,
  castRoutePresentation,
  type CastCharacterDraft,
  type CastRelationshipDraft,
  type CharacterBibleDraft,
} from "../lib/phase32Cast"
import { BookLoader } from "../layout/BookLoader"
import { CastConstraintEditor, CastTextarea } from "./CastEditorFields"
import { CastInspector } from "./CastInspector"

type CastView = "editor" | "graph"
type CastEditorSection = "profile" | "constraints" | "relationships"

type CharacterGraphComponent = ComponentType<{
  artifact: CharacterBibleDraft
  onSelect: (subjectRef: string | null) => void
  selectedId: string | null
}>

export function CastArtifactEditor({
  artifact,
  artifactRef,
  editable,
  onChange,
  revisionLabel,
  routeId,
}: {
  artifact: CharacterBibleDraft
  artifactRef: string
  editable: boolean
  onChange: (value: Record<string, unknown>) => void
  revisionLabel: string
  routeId: CreationRouteId
}) {
  const [selectedSubjectRef, setSelectedSubjectRef] = useState(
    artifact.characters[0]?.subject_ref ?? "",
  )
  const [view, setView] = useState<CastView>("editor")
  const [editorSection, setEditorSection] =
    useState<CastEditorSection>("profile")
  const [Graph, setGraph] = useState<CharacterGraphComponent | null>(null)
  const [graphError, setGraphError] = useState("")
  const copy = castRoutePresentation(routeId)
  const diagnostics = useMemo(() => castDiagnostics(artifact), [artifact])
  const selectedIndex = Math.max(
    0,
    artifact.characters.findIndex(
      (character) => character.subject_ref === selectedSubjectRef,
    ),
  )
  const selected = artifact.characters[selectedIndex]

  useEffect(() => {
    if (
      artifact.characters.some(
        (character) => character.subject_ref === selectedSubjectRef,
      )
    )
      return
    setSelectedSubjectRef(artifact.characters[0]?.subject_ref ?? "")
  }, [artifact.characters, selectedSubjectRef])

  useEffect(() => {
    if (view !== "graph" || Graph || graphError) return
    let active = true
    void import("./CharacterGraph3D")
      .then((module) => {
        if (active) setGraph(() => module.default)
      })
      .catch(() => {
        if (active) setGraphError("3D 人物投影加载失败，请刷新后重试。")
      })
    return () => {
      active = false
    }
  }, [Graph, graphError, view])

  if (!selected) return null

  const patch = (value: Partial<CharacterBibleDraft>) =>
    onChange({ ...artifact, ...value })
  const patchCharacter = (value: Partial<CastCharacterDraft>) =>
    patch({
      characters: artifact.characters.map((character, index) =>
        index === selectedIndex ? { ...character, ...value } : character,
      ),
    })
  const patchRelationship = (
    relationshipIndex: number,
    value: Partial<CastRelationshipDraft>,
  ) =>
    patch({
      relationships: artifact.relationships.map((relationship, index) =>
        index === relationshipIndex
          ? { ...relationship, ...value }
          : relationship,
      ),
    })
  const addRelationship = (targetSubjectRef: string) => {
    if (
      !targetSubjectRef ||
      targetSubjectRef === selected.subject_ref ||
      artifact.relationships.length >= 360 ||
      artifact.relationships.some(
        (relationship) =>
          relationship.from_subject_ref === selected.subject_ref &&
          relationship.to_subject_ref === targetSubjectRef,
      )
    )
      return
    patch({
      relationships: [
        ...artifact.relationships,
        {
          from_subject_ref: selected.subject_ref,
          to_subject_ref: targetSubjectRef,
          pressure: "描述双方当前可观察或共同感知的关系压力。",
          change_trigger: "描述未来可能改变这段关系的可见条件。",
        },
      ],
    })
  }
  const removeRelationship = (relationshipIndex: number) =>
    patch({
      relationships: artifact.relationships.filter(
        (_, index) => index !== relationshipIndex,
      ),
    })
  const related = artifact.relationships
    .map((relationship, relationshipIndex) => ({
      relationship,
      relationshipIndex,
    }))
    .filter(
      ({ relationship }) =>
        relationship.from_subject_ref === selected.subject_ref ||
        relationship.to_subject_ref === selected.subject_ref,
    )

  return (
    <div
      className={`phase32-cast-workbench artifact-mode-surface ${
        editable ? "is-editing" : "is-viewing"
      }`}
    >
      <nav className="phase32-cast-rail" aria-label="人物圣经导航">
        <header>
          <span>
            <UsersRound size={13} /> 人物名册
          </span>
          <strong>{artifact.characters.length}</strong>
        </header>
        <div className="phase32-cast-rail-list">
          {artifact.characters.map((character, index) => {
            const color = graphColorForSubject(character.subject_ref)
            const degree =
              diagnostics.relationshipDegree.get(character.subject_ref) ?? 0
            return (
              <button
                aria-current={
                  character.subject_ref === selected.subject_ref
                    ? "true"
                    : undefined
                }
                className={
                  character.subject_ref === selected.subject_ref
                    ? "is-active"
                    : ""
                }
                key={character.subject_ref}
                onClick={() => setSelectedSubjectRef(character.subject_ref)}
                style={{ "--character-color": color } as CSSProperties}
                type="button"
              >
                <span className="phase32-cast-rail-index">
                  {String(index + 1).padStart(2, "0")}
                </span>
                <span>
                  <strong>{character.display_name}</strong>
                  <small>{character.role}</small>
                </span>
                <i title={`${degree} 条关系`}>{degree}</i>
              </button>
            )
          })}
        </div>
        <footer>
          <Network size={12} />
          <span>稳定身份随聚合根一次提交</span>
        </footer>
      </nav>

      <section className="phase32-cast-workspace">
        <header className="phase32-cast-heading">
          <div>
            <span>{copy.eyebrow}</span>
            <h1>人物身份、欲望与关系压力</h1>
            <p>{copy.lead}</p>
          </div>
          <div className="phase32-cast-view-switch" role="tablist">
            <button
              aria-selected={view === "editor"}
              className={view === "editor" ? "is-active" : ""}
              onClick={() => setView("editor")}
              role="tab"
              type="button"
            >
              <UserRound size={13} /> 人物档案
            </button>
            <button
              aria-selected={view === "graph"}
              className={view === "graph" ? "is-active" : ""}
              onClick={() => setView("graph")}
              role="tab"
              type="button"
            >
              <GitBranch size={13} /> 3D 关系投影
            </button>
          </div>
        </header>

        <div className="phase32-cast-workspace-body">
          {view === "editor" ? (
            <main className="phase32-cast-editor" role="tabpanel">
              <header className="phase32-cast-character-header">
                <div
                  style={
                    {
                      "--character-color": graphColorForSubject(
                        selected.subject_ref,
                      ),
                    } as CSSProperties
                  }
                >
                  <UserRound size={17} />
                </div>
                <span>
                  <small>
                    SUBJECT {String(selectedIndex + 1).padStart(2, "0")}
                  </small>
                  <strong>{selected.display_name}</strong>
                </span>
                <code>{selected.subject_ref}</code>
              </header>

              <nav className="artifact-section-tabs" aria-label="人物档案分区">
                <button
                  className={editorSection === "profile" ? "is-active" : ""}
                  onClick={() => setEditorSection("profile")}
                  type="button"
                >
                  <UserRound size={12} /> 核心档案
                </button>
                <button
                  className={editorSection === "constraints" ? "is-active" : ""}
                  onClick={() => setEditorSection("constraints")}
                  type="button"
                >
                  <ShieldCheck size={12} /> 行动边界
                  <span>{selected.constraints.length}</span>
                </button>
                <button
                  className={
                    editorSection === "relationships" ? "is-active" : ""
                  }
                  onClick={() => setEditorSection("relationships")}
                  type="button"
                >
                  <GitBranch size={12} /> 关系账本
                  <span>{related.length}</span>
                </button>
              </nav>

              {editorSection === "profile" ? (
                <section className="phase32-cast-character-fields">
                  <CastTextarea
                    collaborationPath={`characters.${selectedIndex}.display_name`}
                    collaborationUnit={selected.subject_ref}
                    editable={editable}
                    emphasized
                    label="人物名称"
                    onChange={(display_name) =>
                      patchCharacter({ display_name })
                    }
                    rows={1}
                    value={selected.display_name}
                  />
                  <CastTextarea
                    collaborationPath={`characters.${selectedIndex}.role`}
                    collaborationUnit={selected.subject_ref}
                    editable={editable}
                    emphasized
                    label={copy.roleLabel}
                    onChange={(role) => patchCharacter({ role })}
                    rows={2}
                    value={selected.role}
                  />
                  <div className="phase32-cast-field-pair">
                    <CastTextarea
                      collaborationPath={`characters.${selectedIndex}.desire`}
                      collaborationUnit={selected.subject_ref}
                      editable={editable}
                      label="可观察欲望"
                      onChange={(desire) => patchCharacter({ desire })}
                      rows={3}
                      value={selected.desire}
                    />
                    <CastTextarea
                      collaborationPath={`characters.${selectedIndex}.stakes`}
                      collaborationUnit={selected.subject_ref}
                      editable={editable}
                      label={copy.stakesLabel}
                      onChange={(stakes) => patchCharacter({ stakes })}
                      rows={3}
                      value={selected.stakes}
                    />
                  </div>
                  <div className="phase32-cast-field-pair">
                    <CastTextarea
                      collaborationPath={`characters.${selectedIndex}.voice`}
                      collaborationUnit={selected.subject_ref}
                      editable={editable}
                      label="声音与表达"
                      onChange={(voice) => patchCharacter({ voice })}
                      rows={3}
                      value={selected.voice}
                    />
                    <CastTextarea
                      collaborationPath={`characters.${selectedIndex}.arc_scope`}
                      collaborationUnit={selected.subject_ref}
                      editable={editable}
                      label={copy.arcLabel}
                      onChange={(arc_scope) => patchCharacter({ arc_scope })}
                      rows={3}
                      value={selected.arc_scope}
                    />
                  </div>
                </section>
              ) : null}

              {editorSection === "constraints" ? (
                <CastConstraintEditor
                  constraints={selected.constraints}
                  editable={editable}
                  onChange={(constraints) => patchCharacter({ constraints })}
                  subjectIndex={selectedIndex}
                  subjectRef={selected.subject_ref}
                />
              ) : null}

              {editorSection === "relationships" ? (
                <RelationshipLedger
                  artifact={artifact}
                  editable={editable}
                  onPatch={patchRelationship}
                  onAdd={addRelationship}
                  onRemove={removeRelationship}
                  onSelect={setSelectedSubjectRef}
                  relationships={related}
                  selectedSubjectRef={selected.subject_ref}
                />
              ) : null}
            </main>
          ) : (
            <main className="phase32-cast-graph" role="tabpanel">
              <header>
                <span>
                  <ScanSearch size={13} /> 可重建关系投影
                </span>
                <small>拖拽、旋转与缩放只改变当前视图</small>
              </header>
              <div>
                {Graph ? (
                  <Graph
                    artifact={artifact}
                    onSelect={(subjectRef) => {
                      if (subjectRef) setSelectedSubjectRef(subjectRef)
                    }}
                    selectedId={selectedSubjectRef}
                  />
                ) : graphError ? (
                  <div className="phase32-cast-graph-error">{graphError}</div>
                ) : (
                  <BookLoader
                    variant="compact"
                    label="正在建立人物星图"
                    detail="加载 3D 关系投影"
                  />
                )}
              </div>
            </main>
          )}

          <CastInspector
            artifact={artifact}
            artifactRef={artifactRef}
            revisionLabel={revisionLabel}
            routeId={routeId}
            selectedSubjectRef={selected.subject_ref}
          />
        </div>
      </section>
    </div>
  )
}

function RelationshipLedger({
  artifact,
  editable,
  onAdd,
  onPatch,
  onRemove,
  onSelect,
  relationships,
  selectedSubjectRef,
}: {
  artifact: CharacterBibleDraft
  editable: boolean
  onAdd: (targetSubjectRef: string) => void
  onPatch: (index: number, value: Partial<CastRelationshipDraft>) => void
  onRemove: (index: number) => void
  onSelect: (subjectRef: string) => void
  relationships: Array<{
    relationship: CastRelationshipDraft
    relationshipIndex: number
  }>
  selectedSubjectRef: string
}) {
  const [targetSubjectRef, setTargetSubjectRef] = useState("")
  const availableTargets = artifact.characters.filter(
    (character) =>
      character.subject_ref !== selectedSubjectRef &&
      !artifact.relationships.some(
        (relationship) =>
          relationship.from_subject_ref === selectedSubjectRef &&
          relationship.to_subject_ref === character.subject_ref,
      ),
  )

  return (
    <section className="phase32-cast-relationships">
      <header>
        <span>
          <GitBranch size={13} /> 关系压力与变化触发
        </span>
        <small>{relationships.length} 条当前连接</small>
      </header>
      {editable && availableTargets.length ? (
        <div className="phase32-cast-relationship-composer">
          <select
            aria-label="选择新关系目标人物"
            onChange={(event) => setTargetSubjectRef(event.target.value)}
            value={targetSubjectRef}
          >
            <option value="">选择已登记人物作为关系目标</option>
            {availableTargets.map((character) => (
              <option key={character.subject_ref} value={character.subject_ref}>
                {character.display_name} · {character.role}
              </option>
            ))}
          </select>
          <button
            disabled={!targetSubjectRef}
            onClick={() => {
              onAdd(targetSubjectRef)
              setTargetSubjectRef("")
            }}
            type="button"
          >
            <Plus size={12} /> 新增有向关系
          </button>
        </div>
      ) : null}
      {relationships.length ? (
        <div>
          {relationships.map(({ relationship, relationshipIndex }) => {
            const targetRef =
              relationship.from_subject_ref === selectedSubjectRef
                ? relationship.to_subject_ref
                : relationship.from_subject_ref
            const target = artifact.characters.find(
              (character) => character.subject_ref === targetRef,
            )
            const outgoing =
              relationship.from_subject_ref === selectedSubjectRef
            return (
              <article
                key={`${relationship.from_subject_ref}:${relationship.to_subject_ref}`}
              >
                <header>
                  <button onClick={() => onSelect(targetRef)} type="button">
                    <span>{outgoing ? "指向" : "来自"}</span>
                    <strong>{target?.display_name ?? targetRef}</strong>
                    <ArrowRight size={12} />
                  </button>
                  <code>
                    {relationship.from_subject_ref} →{" "}
                    {relationship.to_subject_ref}
                  </code>
                  {editable ? (
                    <button
                      aria-label={`删除关系 ${relationship.from_subject_ref} 到 ${relationship.to_subject_ref}`}
                      className="phase32-cast-remove-relationship"
                      onClick={() => onRemove(relationshipIndex)}
                      title="删除关系"
                      type="button"
                    >
                      <Trash2 size={12} />
                    </button>
                  ) : null}
                </header>
                <div>
                  <CastTextarea
                    collaborationPath={`relationships.${relationshipIndex}.pressure`}
                    collaborationUnit={selectedSubjectRef}
                    editable={editable}
                    label="当前关系压力"
                    onChange={(pressure) =>
                      onPatch(relationshipIndex, { pressure })
                    }
                    rows={3}
                    value={relationship.pressure}
                  />
                  <CastTextarea
                    collaborationPath={`relationships.${relationshipIndex}.change_trigger`}
                    collaborationUnit={selectedSubjectRef}
                    editable={editable}
                    label="未来变化触发"
                    onChange={(change_trigger) =>
                      onPatch(relationshipIndex, { change_trigger })
                    }
                    rows={3}
                    value={relationship.change_trigger}
                  />
                </div>
              </article>
            )
          })}
        </div>
      ) : (
        <p className="phase32-cast-relationship-empty">
          当前人物尚未进入正式关系。它仍可作为独立角色存在，但会进入阶段审读提示。
        </p>
      )}
    </section>
  )
}
