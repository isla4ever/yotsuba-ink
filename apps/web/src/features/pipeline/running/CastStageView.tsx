import {
  useEffect,
  useMemo,
  useState,
  type ComponentType,
} from "react"
import {
  CheckCircle2,
  ChevronRight,
  Filter,
  Focus,
  GitBranch,
  User,
} from "lucide-react"
import { useApp } from "../state/PipelineAppProvider"
import {
  parseCharacterBibleArtifact,
  type CharacterBibleArtifact,
  type CharacterKind,
  type CharacterRelation,
  type CharacterSubject,
} from "@/features/pipeline/contracts/artifacts"
import {
  CHARACTER_KIND_META,
  relationPresentation,
} from "@/features/pipeline/lib/characterGraph"
import { stageDecisionFor } from "@/features/pipeline/lib/stageDecision"
import { BookLoader } from "@/features/pipeline/layout/BookLoader"
import { useLoadingPresence } from "@/features/pipeline/layout/useLoadingPresence"
import { StageCandidateActions } from "@/features/pipeline/running/StageCandidateActions"
import { useStageArtifactDraft } from "@/features/pipeline/state/useStageArtifactDraft"

type CharacterGraphComponent = ComponentType<{
  artifact: CharacterBibleArtifact
  onSelect: (subjectId: string | null) => void
  selectedId: string | null
}>

export default function CastStageView() {
  const {
    activeProject,
    activeRun,
    refreshRun,
    runArtifactError,
    runArtifactLoading,
    runArtifacts,
    runCandidateArtifacts,
    runLoading,
    selectedChar,
    setRoute,
    setSelectedChar,
  } = useApp()
  const [filterKind, setFilterKind] = useState<CharacterKind | "all">("all")
  const [CharacterGraph3D, setCharacterGraph3D] =
    useState<CharacterGraphComponent | null>(null)
  const [graphLoadError, setGraphLoadError] = useState("")
  const decision = useMemo(
    () => stageDecisionFor(activeRun, "cast"),
    [activeRun],
  )
  const committed = runArtifacts.cast
  const candidate = runCandidateArtifacts.cast
  const source = decision ? candidate : committed
  const runId = activeRun?.definition.run_id ?? ""
  const draft = useStageArtifactDraft(runId, decision, source)
  const parsed = useMemo(
    () => parseCharacterBibleArtifact(draft.artifact ?? source?.payload),
    [draft.artifact, source],
  )
  const artifact = parsed.artifact
  const subjectSignature =
    artifact?.subjects.map((subject) => subject.id).join("|") ?? ""

  useEffect(() => {
    if (!artifact?.subjects.length) return
    if (!artifact.subjects.some((subject) => subject.id === selectedChar))
      setSelectedChar(artifact.subjects[0].id)
  }, [artifact, selectedChar, setSelectedChar, subjectSignature])

  useEffect(() => {
    let active = true
    void import("@/features/pipeline/running/CharacterGraph3D")
      .then((module) => {
        if (active) setCharacterGraph3D(() => module.default)
      })
      .catch(() => {
        if (active) setGraphLoadError("3D 人物关系图谱加载失败，请刷新后重试。")
      })
    return () => {
      active = false
    }
  }, [])

  const initialLoad = useLoadingPresence(runLoading || runArtifactLoading)
  const graphLoad = useLoadingPresence(
    !CharacterGraph3D && !graphLoadError,
  )

  if (initialLoad.visible) {
    return (
      <BookLoader
        phase={initialLoad.exiting ? "exit" : "enter"}
        variant="panel"
        label="正在同步人物编排"
        detail="读取 Character Bible 与正式关系"
      />
    )
  }

  if (!activeProject?.latestRunId || !activeRun) {
    return (
      <CastEmpty
        title="当前作品尚未启动创作 Run"
        detail="人物编排会在故事脊柱确认后生成。"
        onBack={() => setRoute("studio")}
      />
    )
  }

  if (runArtifactError || !source) {
    return (
      <CastEmpty
        title="尚未取得人物编排 Artifact"
        detail={runArtifactError || "请先完成故事脊柱，并等待人物阶段生成。"}
        onBack={() => setRoute("spine")}
      />
    )
  }

  if (!artifact) {
    return (
      <CastEmpty
        title="人物编排合同校验失败"
        detail={parsed.error}
        onBack={() => setRoute("run-monitor")}
      />
    )
  }

  const subject =
    artifact.subjects.find((item) => item.id === selectedChar) ??
    artifact.subjects[0]
  const filtered =
    filterKind === "all"
      ? artifact.subjects
      : artifact.subjects.filter((item) => item.kind === filterKind)
  const subjectRelations = artifact.relations
    .map((relation, relationIndex) => ({ ...relation, relationIndex }))
    .filter((relation) => relation.a === subject.id || relation.b === subject.id)
  const relationLegend = Array.from(
    new Map(
      artifact.relations.map((relation) => {
        const presentation = relationPresentation(relation.type)
        return [relation.type, presentation] as const
      }),
    ).entries(),
  )
  const editable = Boolean(decision && candidate)

  return (
    <div className="cast-screen page-in">
      <header className="cast-stage-bar stage-aura">
        <div className="cast-stage-status">
          <CheckCircle2
            size={13}
            className={decision ? "text-action" : "text-mint"}
          />
          <strong className={decision ? "text-action" : "text-mint"}>
            {decision ? "人物候选待确认" : "人物已定稿"}
          </strong>
          <span>
            · {artifact.subjects.length} 个登记主体 ·{" "}
            {artifact.relations.length} 条正式关系
          </span>
        </div>
        {decision ? (
          <StageCandidateActions
            acceptLabel="确认人物编排"
            artifact={artifact as unknown as Record<string, unknown>}
            decision={decision}
            disabled={!editable}
            draftStatus={draft.status}
            onResolved={refreshRun}
            regenerateDescription="只调整人物文学字段与既有关系压力；主体身份、登场范围和关系端点继续使用冻结合同。"
            regeneratePlaceholder="例如：让主角与导师的冲突更具体，并强化两人在中段决裂的行动代价。"
            regenerateTitle="定向重做人物编排"
            runId={runId}
          />
        ) : (
          <button
            type="button"
            onClick={() => setRoute("volumes")}
            className="btn btn-primary text-xs"
          >
            查看分卷架构 <ChevronRight size={14} />
          </button>
        )}
      </header>

      {(draft.error || runArtifactError) && (
        <div className="mx-4 md:mx-5 mt-3 banner-warning" role="alert">
          {draft.error || runArtifactError}
        </div>
      )}

      <div className="cast-workbench">
        <aside className="cast-roster" aria-label="人物名册">
          <div className="cast-roster-filter">
            <Filter size={12} />
            <select
              value={filterKind}
              onChange={(event) =>
                setFilterKind(event.target.value as CharacterKind | "all")
              }
              aria-label="筛选人物类型"
            >
              <option value="all">全部主体</option>
              {Object.entries(CHARACTER_KIND_META).map(([kind, meta]) => (
                <option key={kind} value={kind}>
                  {meta.label}
                </option>
              ))}
            </select>
          </div>
          <nav>
            {filtered.map((item) => {
              const meta = CHARACTER_KIND_META[item.kind]
              return (
                <button
                  key={item.id}
                  type="button"
                  className={item.id === subject.id ? "active" : ""}
                  onClick={() => setSelectedChar(item.id)}
                >
                  <span
                    className="cast-roster-node"
                    style={
                      { "--subject-color": meta.color } as React.CSSProperties
                    }
                  />
                  <span>
                    <strong>{item.name}</strong>
                    <small>
                      {meta.label} · {formatDebut(item.debut)}
                    </small>
                  </span>
                </button>
              )
            })}
          </nav>
        </aside>

        <CharacterDossier
          artifact={artifact}
          editable={editable}
          onArtifactChange={draft.change}
          onSelect={setSelectedChar}
          relations={subjectRelations}
          subject={subject}
        />

        <section className="cast-graph-stage" aria-label="人物关系图谱">
          <header className="cast-graph-toolbar">
            <div>
              <GitBranch size={13} />
              <strong>关系图谱</strong>
              <span>3D</span>
            </div>
            {selectedChar && (
              <button type="button" onClick={() => setSelectedChar(null)}>
                <Focus size={12} />
                取消聚焦
              </button>
            )}
          </header>
          <div className="cast-graph-viewport">
            {graphLoad.visible ? (
              <BookLoader
                phase={graphLoad.exiting ? "exit" : "enter"}
                variant="compact"
                label="正在建立人物星图"
                detail="加载 3D 关系投影"
              />
            ) : CharacterGraph3D ? (
              <CharacterGraph3D
                artifact={artifact}
                selectedId={selectedChar}
                onSelect={setSelectedChar}
              />
            ) : (
              <div className="h-full grid place-items-center p-6 text-xs text-fog">
                {graphLoadError}
              </div>
            )}
            <div className="cast-relation-legend" aria-label="关系类型图例">
              {relationLegend.map(([type, meta]) => (
                <span key={type}>
                  <i style={{ backgroundColor: meta.color }} />
                  {meta.label}
                </span>
              ))}
            </div>
          </div>
        </section>
      </div>
    </div>
  )
}

function CharacterDossier({
  artifact,
  editable,
  onArtifactChange,
  onSelect,
  relations,
  subject,
}: {
  artifact: CharacterBibleArtifact
  editable: boolean
  onArtifactChange: (artifact: Record<string, unknown>) => void
  onSelect: (id: string | null) => void
  relations: Array<CharacterRelation & { relationIndex: number }>
  subject: CharacterSubject
}) {
  const meta = CHARACTER_KIND_META[subject.kind]
  const subjectIndex = artifact.subjects.findIndex(
    (item) => item.id === subject.id,
  )
  const updateSubject = (
    field: CharacterTextField,
    value: string,
  ) => {
    if (!editable || subjectIndex < 0) return
    onArtifactChange({
      ...artifact,
      subjects: artifact.subjects.map((item, index) =>
        index === subjectIndex ? { ...item, [field]: value } : item,
      ),
    } as unknown as Record<string, unknown>)
  }
  const updateRelation = (
    relationIndex: number,
    patch: Partial<Pick<CharacterRelation, "pressure" | "type">>,
  ) => {
    if (!editable || relationIndex < 0) return
    onArtifactChange({
      ...artifact,
      relations: artifact.relations.map((relation, index) =>
        index === relationIndex ? { ...relation, ...patch } : relation,
      ),
    } as unknown as Record<string, unknown>)
  }
  return (
    <aside className="cast-dossier" aria-label={`${subject.name}人物档案`}>
      <header>
        <div
          className="cast-dossier-avatar"
          style={{ "--subject-color": meta.color } as React.CSSProperties}
        >
          <User size={16} />
        </div>
        <div>
          <strong>{subject.name}</strong>
          <small>{subject.id}</small>
        </div>
        <span className={`badge ${meta.badge}`}>{meta.label}</span>
      </header>
      <div className="cast-dossier-scroll">
        <DossierField editable={editable} field="function" label="叙事职责" onChange={updateSubject} subjectIndex={subjectIndex} unitRef={subject.id} value={subject.function} />
        <DossierField editable={editable} field="background" label="故事前史" onChange={updateSubject} subjectIndex={subjectIndex} unitRef={subject.id} value={subject.background} />
        <DossierField editable={editable} field="conflict_history" label="冲突历史" onChange={updateSubject} subjectIndex={subjectIndex} unitRef={subject.id} value={subject.conflict_history} />
        <DossierField editable={editable} field="present_stakes" label="当下利害" onChange={updateSubject} subjectIndex={subjectIndex} unitRef={subject.id} value={subject.present_stakes} />
        <DossierField editable={editable} field="temperament" label="性格反应" onChange={updateSubject} subjectIndex={subjectIndex} unitRef={subject.id} value={subject.temperament} />
        <DossierField editable={editable} field="speech_style" label="说话方式" onChange={updateSubject} subjectIndex={subjectIndex} unitRef={subject.id} value={subject.speech_style} />
        <DossierField editable={editable} field="drive" label="行动驱力" onChange={updateSubject} subjectIndex={subjectIndex} unitRef={subject.id} value={subject.drive} />
        <DossierField editable={editable} field="change" label="人物变化" onChange={updateSubject} subjectIndex={subjectIndex} unitRef={subject.id} value={subject.change} />
        <div className="cast-dossier-field">
          <span>首次登场</span>
          <p>{formatDebut(subject.debut)}</p>
        </div>
        <div className="cast-dossier-field">
          <span>边界限制</span>
          <div className="cast-limit-list">
            {subject.limits.map((limit) => (
              <em key={limit}>{limit}</em>
            ))}
          </div>
        </div>
        <div className="cast-dossier-field">
          <span>关系邻域 · {relations.length}</span>
          <div className="cast-relation-list">
            {relations.map((relation) => {
              const targetId =
                relation.a === subject.id ? relation.b : relation.a
              const target = artifact.subjects.find(
                (item) => item.id === targetId,
              )
              const presentation = relationPresentation(relation.type)
              return editable ? (
                <div
                  className="cast-relation-editor"
                  key={`${relation.a}-${relation.b}`}
                >
                  <i style={{ backgroundColor: presentation.color }} />
                  <button
                    type="button"
                    className="cast-relation-target"
                    onClick={() => onSelect(targetId)}
                  >
                    <strong>{target?.name ?? targetId}</strong>
                    <ChevronRight size={12} />
                  </button>
                  <label>
                    <span>关系类型</span>
                    <input
                      aria-label={`${target?.name ?? targetId} 关系类型`}
                      data-collaboration-field-path={`relations.${relation.relationIndex}.type`}
                      data-collaboration-unit={subject.id}
                      value={relation.type}
                      onChange={(event) =>
                        updateRelation(relation.relationIndex, {
                          type: event.target.value,
                        })
                      }
                    />
                  </label>
                  <label>
                    <span>关系压力</span>
                    <textarea
                      aria-label={`${target?.name ?? targetId} 关系压力`}
                      data-collaboration-field-path={`relations.${relation.relationIndex}.pressure`}
                      data-collaboration-unit={subject.id}
                      rows={3}
                      value={relation.pressure}
                      onChange={(event) =>
                        updateRelation(relation.relationIndex, {
                          pressure: event.target.value,
                        })
                      }
                    />
                  </label>
                </div>
              ) : (
                <button
                  key={`${relation.a}-${relation.b}`}
                  type="button"
                  onClick={() => onSelect(targetId)}
                >
                  <i style={{ backgroundColor: presentation.color }} />
                  <span>
                    <strong>{target?.name ?? targetId}</strong>
                    <small>
                      {presentation.label} · {relation.pressure}
                    </small>
                  </span>
                  <ChevronRight size={12} />
                </button>
              )
            })}
          </div>
        </div>
      </div>
    </aside>
  )
}

type CharacterTextField =
  | "function"
  | "background"
  | "conflict_history"
  | "present_stakes"
  | "temperament"
  | "speech_style"
  | "drive"
  | "change"

function DossierField({
  editable,
  field,
  label,
  onChange,
  subjectIndex,
  unitRef,
  value,
}: {
  editable: boolean
  field: CharacterTextField
  label: string
  onChange: (field: CharacterTextField, value: string) => void
  subjectIndex: number
  unitRef: string
  value: string
}) {
  return (
    <div className="cast-dossier-field">
      <span>{label}</span>
      <textarea
        aria-label={`${unitRef} ${label}`}
        data-collaboration-field-path={`subjects.${subjectIndex}.${field}`}
        data-collaboration-unit={unitRef}
        onChange={(event) => onChange(field, event.target.value)}
        readOnly={!editable}
        rows={3}
        value={value}
      />
    </div>
  )
}

function CastEmpty({
  detail,
  onBack,
  title,
}: {
  detail: string
  onBack: () => void
  title: string
}) {
  return (
    <div className="flex-1 grid place-items-center p-6 page-in">
      <div className="max-w-md text-center">
        <User size={22} className="text-fog mx-auto mb-3" />
        <h1 className="text-sm font-semibold text-ink mb-1">{title}</h1>
        <p className="text-xs text-fog mb-4">{detail}</p>
        <button
          type="button"
          className="btn btn-secondary text-xs"
          onClick={onBack}
        >
          返回
        </button>
      </div>
    </div>
  )
}

function formatDebut(value: string) {
  const match = /^chapter:(\d+)(?:-(\d+))?$/.exec(value)
  if (!match) return value
  return match[2] ? `第 ${match[1]}–${match[2]} 章` : `第 ${match[1]} 章`
}
