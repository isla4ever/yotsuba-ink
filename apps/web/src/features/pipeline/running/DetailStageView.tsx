import { useEffect, useMemo, useState, type ReactNode } from "react"
import {
  AlertTriangle,
  ArrowRight,
  BookOpen,
  CheckCircle2,
  CircleStop,
  CornerDownRight,
  GitCommitHorizontal,
  Lock,
  MapPin,
  Plus,
  Sparkles,
  Swords,
  Target,
  Trash2,
  UsersRound,
} from "lucide-react"
import { useApp } from "../state/PipelineAppProvider"
import {
  parseCharacterBibleArtifact,
  parseDetailArtifact,
  type DetailArtifact,
  type DetailChapter,
  type DetailScene,
} from "@/features/pipeline/contracts/artifacts"
import { BookLoader } from "@/features/pipeline/layout/BookLoader"
import { useLoadingPresence } from "@/features/pipeline/layout/useLoadingPresence"
import {
  detailChapterProgress,
  orderedNumber,
  stageDraftStatusLabel,
} from "@/features/pipeline/lib/detailPresentation"
import { stageDecisionFor } from "@/features/pipeline/lib/stageDecision"
import { resolveRunDecision } from "@/features/pipeline/services/runApi"
import { useStageArtifactDraft } from "@/features/pipeline/state/useStageArtifactDraft"

type DialogKind = "regenerate" | "cancel" | null
type ActionState = "idle" | "accepting" | "regenerating" | "cancelling"

const EMPTY_SCENE: DetailScene = {
  place: "待定场景",
  objective: "补充本场目标",
  conflict: "补充本场阻力",
  turn: "补充可见转折",
  result: "补充场景结果",
}

export default function DetailStageView() {
  const {
    activeProject,
    activeRun,
    refreshRun,
    runArtifactError,
    runArtifactLoading,
    runArtifacts,
    runCandidateArtifacts,
    runChapters,
    runLoading,
    selectedChapter,
    setRoute,
    setSelectedChapter,
  } = useApp()
  const decision = useMemo(
    () => stageDecisionFor(activeRun, "detail"),
    [activeRun],
  )
  const committed = runArtifacts.detail
  const candidate = runCandidateArtifacts.detail
  const source = decision ? candidate : committed
  const runId = activeRun?.definition.run_id ?? ""
  const draft = useStageArtifactDraft(runId, decision, source)
  const decoded = useMemo(
    () => parseDetailArtifact(draft.artifact ?? source?.payload),
    [draft.artifact, source],
  )
  const cast = useMemo(
    () => parseCharacterBibleArtifact(runArtifacts.cast?.payload),
    [runArtifacts.cast],
  )
  const [workingArtifact, setWorkingArtifact] = useState<DetailArtifact | null>(
    null,
  )
  const [selectedSceneIndex, setSelectedSceneIndex] = useState(0)
  const [dialog, setDialog] = useState<DialogKind>(null)
  const [direction, setDirection] = useState("")
  const [actionState, setActionState] = useState<ActionState>("idle")
  const [actionError, setActionError] = useState("")

  useEffect(() => {
    if (decoded.artifact) setWorkingArtifact(decoded.artifact)
  }, [decoded.artifact, source?.artifact_id])

  const artifact = workingArtifact ?? decoded.artifact
  const chapterSignature =
    artifact?.chapters.map((chapter) => chapter.ref).join("|") ?? ""

  useEffect(() => {
    if (!artifact?.chapters.length) return
    if (!artifact.chapters.some((chapter) => chapter.ref === selectedChapter)) {
      setSelectedChapter(artifact.chapters[0].ref)
      setSelectedSceneIndex(0)
    }
  }, [artifact, chapterSignature, selectedChapter, setSelectedChapter])

  const initialLoad = useLoadingPresence(runLoading || runArtifactLoading)

  if (initialLoad.visible) {
    return (
      <BookLoader
        phase={initialLoad.exiting ? "exit" : "enter"}
        variant="panel"
        label="正在展开章节施工图"
        detail="同步章节槽位、场景任务与跨章交接"
      />
    )
  }

  if (!activeProject?.latestRunId || !activeRun) {
    return (
      <DetailEmpty
        title="当前作品尚未启动创作 Run"
        detail="分卷架构确认后，系统才会生成章节施工图。"
        action="返回作品库"
        onAction={() => setRoute("studio")}
      />
    )
  }

  if (!source || !artifact) {
    return (
      <DetailEmpty
        title="章节施工图尚未就绪"
        detail={
          runArtifactError ||
          decoded.error ||
          "请先完成分卷阶段并等待 Detail Artifact。"
        }
        action="查看分卷架构"
        onAction={() => setRoute("volumes")}
      />
    )
  }

  const chapter =
    artifact.chapters.find((item) => item.ref === selectedChapter) ??
    artifact.chapters[0]
  const chapterIndex = Math.max(
    0,
    artifact.chapters.findIndex((item) => item.ref === chapter.ref),
  )
  const sceneIndex = Math.min(selectedSceneIndex, chapter.scenes.length - 1)
  const scene = chapter.scenes[sceneIndex]
  const editable = Boolean(decision && candidate)
  const validated = parseDetailArtifact(artifact)
  const acceptedChapterIds = new Set(
    runChapters
      .filter((record) =>
        ["accepted", "edited", "branched"].includes(
          String(record.artifact.author_status),
        ),
      )
      .map((record) => record.chapter_id),
  )
  const volumeCount = new Set(artifact.chapters.map((item) => item.volume_ref))
    .size
  const castNames = new Map(
    cast.artifact?.subjects.map((subject) => [subject.id, subject.name]) ?? [],
  )

  const changeArtifact = (next: DetailArtifact) => {
    setWorkingArtifact(next)
    const nextValidation = parseDetailArtifact(next)
    if (nextValidation.artifact)
      draft.change(next as unknown as Record<string, unknown>)
  }

  const updateChapter = (patch: Partial<DetailChapter>) => {
    changeArtifact({
      chapters: artifact.chapters.map((item, index) =>
        index === chapterIndex ? { ...item, ...patch } : item,
      ),
    })
  }

  const updateScene = (patch: Partial<DetailScene>) => {
    updateChapter({
      scenes: chapter.scenes.map((item, index) =>
        index === sceneIndex ? { ...item, ...patch } : item,
      ),
    })
  }

  const addScene = () => {
    if (!editable || chapter.scenes.length >= 12) return
    updateChapter({ scenes: [...chapter.scenes, { ...EMPTY_SCENE }] })
    setSelectedSceneIndex(chapter.scenes.length)
  }

  const removeScene = () => {
    if (!editable || chapter.scenes.length <= 1) return
    updateChapter({
      scenes: chapter.scenes.filter((_, index) => index !== sceneIndex),
    })
    setSelectedSceneIndex(Math.max(0, sceneIndex - 1))
  }

  const submitDecision = async (action: "accept" | "regenerate" | "cancel") => {
    if (!decision || actionState !== "idle") return
    if (action === "accept" && !validated.artifact) {
      setActionError(validated.error || "当前细纲未通过合同校验")
      return
    }
    if (action === "regenerate" && !direction.trim()) {
      setActionError("请先填写本次换稿方向")
      return
    }
    setActionState(
      action === "accept"
        ? "accepting"
        : action === "regenerate"
          ? "regenerating"
          : "cancelling",
    )
    setActionError("")
    try {
      await resolveRunDecision(
        runId,
        decision.decisionId,
        action,
        decision.domainRevision,
        action === "accept"
          ? validated.artifact as unknown as Record<string, unknown>
          : undefined,
        action === "regenerate" ? direction : undefined,
      )
      setDialog(null)
      setDirection("")
      await refreshRun()
    } catch (reason) {
      setActionError(
        reason instanceof Error ? reason.message : "细纲决策提交失败",
      )
    } finally {
      setActionState("idle")
    }
  }

  return (
    <div className="flex-1 overflow-hidden flex flex-col page-in">
      <header className="stage-aura border-b border-hairline bg-surface px-4 md:px-6 py-3 flex items-center gap-2 shrink-0">
        <div className="flex items-center gap-2 flex-1 min-w-0">
          {decision ? (
            <AlertTriangle size={14} className="text-amber shrink-0" />
          ) : (
            <CheckCircle2 size={14} className="text-mint shrink-0" />
          )}
          <div className="min-w-0">
            <strong className="block text-xs text-ink">
              {decision ? "细纲候选待确认" : "章节施工图已定稿"}
            </strong>
            <span className="block text-[10px] text-fog truncate">
              {artifact.chapters.length} 章 · {volumeCount} 卷 · 已成稿{" "}
              {acceptedChapterIds.size} 章
              {decision ? ` · ${stageDraftStatusLabel(draft.status)}` : ""}
            </span>
          </div>
        </div>
        {decision ? (
          <>
            {decision.allowedActions.includes("regenerate") && (
              <button
                type="button"
                className="btn btn-secondary text-xs hidden sm:inline-flex"
                onClick={() => setDialog("regenerate")}
              >
                <Sparkles size={12} /> 定向换稿
              </button>
            )}
            {decision.allowedActions.includes("cancel") && (
              <button
                type="button"
                className="btn btn-ghost text-risk text-xs hidden sm:inline-flex"
                onClick={() => setDialog("cancel")}
              >
                <CircleStop size={12} /> 取消
              </button>
            )}
            <button
              type="button"
              className="btn btn-primary text-xs"
              disabled={!validated.artifact || actionState !== "idle"}
              onClick={() => void submitDecision("accept")}
            >
              <Lock size={12} />
              {actionState === "accepting" ? "定稿中…" : "确认定稿"}
            </button>
          </>
        ) : (
          <button
            type="button"
            className="btn btn-primary text-xs"
            onClick={() => setRoute("text")}
          >
            进入正文 <ArrowRight size={12} />
          </button>
        )}
      </header>

      <div className="flex-1 overflow-hidden flex min-h-0">
        <ChapterLedger
          artifact={artifact}
          activeRun={activeRun}
          runChapters={runChapters}
          selectedChapter={chapter.ref}
          onSelect={(chapterRef) => {
            setSelectedChapter(chapterRef)
            setSelectedSceneIndex(0)
          }}
        />

        <main className="flex-1 overflow-hidden flex flex-col min-w-0">
          <div className="border-b border-ghost px-4 py-2.5 bg-surface shrink-0">
            <div className="md:hidden mb-2">
              <select
                aria-label="选择章节"
                className="input text-xs w-full"
                value={chapter.ref}
                onChange={(event) => {
                  setSelectedChapter(event.target.value)
                  setSelectedSceneIndex(0)
                }}
              >
                {artifact.chapters.map((item) => (
                  <option key={item.ref} value={item.ref}>
                    第 {orderedNumber(item.ref)} 章 · {item.title}
                  </option>
                ))}
              </select>
            </div>
            <div className="flex items-center gap-2 min-w-0">
              <span className="font-mono text-xs text-fog shrink-0">
                CH{String(orderedNumber(chapter.ref)).padStart(2, "0")}
              </span>
              <strong className="text-sm text-ink truncate">
                《{chapter.title}》
              </strong>
              <span className="text-[10px] text-fog hidden lg:inline">
                {chapter.volume_ref} ·{" "}
                {castNames.get(chapter.pov) ?? chapter.pov} 视角 · 正文预算{" "}
                {chapter.target_characters?.toLocaleString() ?? "待定"} 字
              </span>
              <div className="flex gap-1 ml-auto shrink-0">
                {chapter.scenes.map((_, index) => (
                  <button
                    type="button"
                    key={`${chapter.ref}-scene-${index + 1}`}
                    aria-label={`场景 ${index + 1}`}
                    aria-pressed={sceneIndex === index}
                    onClick={() => setSelectedSceneIndex(index)}
                    className={`text-[10px] min-w-7 px-2 py-1 rounded transition-colors ${
                      sceneIndex === index
                        ? "text-white"
                        : "bg-hover text-fog hover:text-ink"
                    }`}
                    style={
                      sceneIndex === index
                        ? { background: "var(--mode-primary)" }
                        : undefined
                    }
                  >
                    S{index + 1}
                  </button>
                ))}
                {editable && chapter.scenes.length < 12 && (
                  <button
                    type="button"
                    aria-label="新增场景"
                    className="text-[10px] min-w-7 px-2 py-1 rounded bg-hover text-fog hover:text-ink"
                    onClick={addScene}
                  >
                    <Plus size={11} />
                  </button>
                )}
              </div>
            </div>
          </div>

          <div className="flex-1 overflow-y-auto p-4 md:p-5">
            <section className="max-w-6xl mx-auto space-y-4 animate-fade-in">
              <div className="grid grid-cols-1 lg:grid-cols-[minmax(0,0.7fr)_minmax(0,1.3fr)] gap-3">
                <Field label="章名">
                  <input
                    className="input text-sm w-full"
                    value={chapter.title}
                    readOnly={!editable}
                    minLength={2}
                    maxLength={12}
                    onChange={(event) =>
                      updateChapter({ title: event.target.value })
                    }
                  />
                </Field>
                <Field label="章节目的">
                  <textarea
                    className="w-full bg-transparent text-sm text-ink outline-none resize-y leading-relaxed min-h-14"
                    data-collaboration-field-path={`chapters.${chapterIndex}.purpose`}
                    data-collaboration-unit={chapter.ref}
                    value={chapter.purpose}
                    readOnly={!editable}
                    rows={2}
                    onChange={(event) =>
                      updateChapter({ purpose: event.target.value })
                    }
                  />
                </Field>
              </div>

              <div className="bg-surface border border-hairline rounded-lg px-4 py-3 flex flex-wrap gap-x-5 gap-y-2">
                <Meta
                  icon={<UsersRound size={12} />}
                  label="POV"
                  value={castNames.get(chapter.pov) ?? chapter.pov}
                />
                <Meta
                  icon={<Target size={12} />}
                  label="正文预算"
                  value={`${chapter.target_characters?.toLocaleString() ?? "待定"} 字`}
                />
                <Meta
                  icon={<GitCommitHorizontal size={12} />}
                  label="冻结转折"
                  value={chapter.turn_refs.join(" · ")}
                />
                <Meta
                  icon={<UsersRound size={12} />}
                  label="出场主体"
                  value={chapter.cast_ids
                    .map((id) => castNames.get(id) ?? id)
                    .join(" · ")}
                />
              </div>

              <div className="flex items-center justify-between">
                <div>
                  <span className="text-[10px] uppercase text-fog">
                    Scene blueprint
                  </span>
                  <h2 className="text-sm font-semibold text-ink mt-0.5">
                    场景 {sceneIndex + 1}
                  </h2>
                </div>
                {editable && chapter.scenes.length > 1 && (
                  <button
                    type="button"
                    className="btn btn-ghost text-risk text-xs"
                    onClick={removeScene}
                  >
                    <Trash2 size={12} /> 删除场景
                  </button>
                )}
              </div>

              <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-5 gap-3">
                <SceneField
                  icon={<MapPin size={12} />}
                  label="场所 PLACE"
                  value={scene.place}
                  editable={editable}
                  fieldPath={`chapters.${chapterIndex}.scenes.${sceneIndex}.place`}
                  onChange={(value) => updateScene({ place: value })}
                  unitRef={chapter.ref}
                />
                <SceneField
                  icon={<Target size={12} />}
                  label="目标 OBJECTIVE"
                  value={scene.objective}
                  editable={editable}
                  fieldPath={`chapters.${chapterIndex}.scenes.${sceneIndex}.objective`}
                  onChange={(value) => updateScene({ objective: value })}
                  unitRef={chapter.ref}
                />
                <SceneField
                  icon={<Swords size={12} />}
                  label="冲突 CONFLICT"
                  value={scene.conflict}
                  editable={editable}
                  fieldPath={`chapters.${chapterIndex}.scenes.${sceneIndex}.conflict`}
                  onChange={(value) => updateScene({ conflict: value })}
                  unitRef={chapter.ref}
                />
                <SceneField
                  icon={<GitCommitHorizontal size={12} />}
                  label="转折 TURN"
                  value={scene.turn}
                  editable={editable}
                  fieldPath={`chapters.${chapterIndex}.scenes.${sceneIndex}.turn`}
                  onChange={(value) => updateScene({ turn: value })}
                  unitRef={chapter.ref}
                />
                <SceneField
                  icon={<CheckCircle2 size={12} />}
                  label="结果 RESULT"
                  value={scene.result}
                  editable={editable}
                  fieldPath={`chapters.${chapterIndex}.scenes.${sceneIndex}.result`}
                  onChange={(value) => updateScene({ result: value })}
                  unitRef={chapter.ref}
                />
              </div>

              <Field
                label="跨章交接 HANDOFF"
                icon={<CornerDownRight size={12} />}
              >
                <textarea
                  className="w-full bg-transparent text-sm text-ink outline-none resize-y leading-relaxed min-h-16"
                  data-collaboration-field-path={`chapters.${chapterIndex}.handoff`}
                  data-collaboration-unit={chapter.ref}
                  value={chapter.handoff}
                  readOnly={!editable}
                  rows={2}
                  onChange={(event) =>
                    updateChapter({ handoff: event.target.value })
                  }
                />
              </Field>

              {(!validated.artifact || draft.error || actionError) && (
                <div
                  role="alert"
                  className="border border-risk/40 bg-risk/10 rounded-lg px-4 py-3 text-xs text-risk"
                >
                  {actionError || draft.error || validated.error}
                </div>
              )}
              {!editable && (
                <p className="text-[10px] text-fog text-center">
                  此处展示已定稿 Detail
                  Artifact；正文只能执行这些章节槽位、转折与交接。
                </p>
              )}
            </section>
          </div>
        </main>
      </div>

      {dialog && decision && (
        <DecisionDialog
          kind={dialog}
          direction={direction}
          busy={actionState !== "idle"}
          error={actionError}
          onDirection={setDirection}
          onClose={() => {
            if (actionState !== "idle") return
            setDialog(null)
            setActionError("")
          }}
          onConfirm={() =>
            void submitDecision(dialog === "cancel" ? "cancel" : "regenerate")
          }
        />
      )}
    </div>
  )
}

function ChapterLedger({
  artifact,
  activeRun,
  runChapters,
  selectedChapter,
  onSelect,
}: {
  artifact: DetailArtifact
  activeRun: NonNullable<ReturnType<typeof useApp>["activeRun"]>
  runChapters: ReturnType<typeof useApp>["runChapters"]
  selectedChapter: string
  onSelect: (chapterRef: string) => void
}) {
  return (
    <aside
      className="hidden md:flex flex-col w-52 border-r border-hairline bg-surface overflow-hidden shrink-0"
      aria-label="章节施工台账"
    >
      <div className="px-3 py-2 border-b border-ghost shrink-0">
        <div className="text-[10px] text-fog uppercase">
          章节施工台账 · {artifact.chapters.length}
        </div>
      </div>
      <nav className="flex-1 overflow-y-auto p-2 space-y-0.5">
        {artifact.chapters.map((chapter, index) => {
          const active = chapter.ref === selectedChapter
          const progress = detailChapterProgress(
            chapter.ref,
            runChapters,
            activeRun.read_model.pending_decisions,
          )
          const previousVolume = artifact.chapters[index - 1]?.volume_ref
          return (
            <div key={chapter.ref}>
              {previousVolume !== chapter.volume_ref && (
                <div className="px-3 pt-3 pb-1 text-[10px] text-action uppercase">
                  Volume {orderedNumber(chapter.volume_ref)}
                </div>
              )}
              <button
                type="button"
                onClick={() => onSelect(chapter.ref)}
                className={`w-full text-left px-3 py-2.5 rounded-lg border transition-colors ${
                  active
                    ? "bg-elev border-hairline"
                    : "border-transparent hover:bg-hover"
                }`}
              >
                <div className="flex items-center justify-between gap-2 mb-1">
                  <span className="font-mono text-[10px] text-fog">
                    CH{String(index + 1).padStart(2, "0")}
                  </span>
                  <span className={`text-[10px] ${progress.className}`}>
                    {progress.label}
                  </span>
                </div>
                <div className="text-xs text-ink truncate">
                  《{chapter.title}》
                </div>
                <div className="text-[10px] text-fog mt-1 truncate">
                  {chapter.scenes.length} 场 ·{" "}
                  {chapter.target_characters?.toLocaleString() ?? "待定"} 字
                </div>
              </button>
            </div>
          )
        })}
      </nav>
    </aside>
  )
}

function Field({
  label,
  icon,
  children,
}: {
  label: string
  icon?: ReactNode
  children: ReactNode
}) {
  return (
    <label className="block bg-surface border border-hairline rounded-lg px-4 py-3">
      <span className="flex items-center gap-1.5 text-[10px] text-fog mb-1.5">
        {icon} {label}
      </span>
      {children}
    </label>
  )
}

function Meta({
  icon,
  label,
  value,
}: {
  icon: ReactNode
  label: string
  value: string
}) {
  return (
    <div className="min-w-0 flex items-start gap-2 text-xs">
      <span className="text-action mt-0.5 shrink-0">{icon}</span>
      <div className="min-w-0">
        <span className="block text-[10px] text-fog">{label}</span>
        <strong className="block text-ink font-medium break-words">
          {value}
        </strong>
      </div>
    </div>
  )
}

function SceneField({
  icon,
  label,
  value,
  editable,
  fieldPath,
  onChange,
  unitRef,
}: {
  icon: ReactNode
  label: string
  value: string
  editable: boolean
  fieldPath: string
  onChange: (value: string) => void
  unitRef: string
}) {
  return (
    <label className="bg-surface border border-hairline rounded-lg p-3 min-w-0">
      <span className="flex items-center gap-1.5 text-[10px] text-action mb-1.5">
        {icon} {label}
      </span>
      <textarea
        className="w-full bg-transparent text-xs text-ink outline-none resize-y leading-relaxed min-h-24"
        data-collaboration-field-path={fieldPath}
        data-collaboration-unit={unitRef}
        value={value}
        readOnly={!editable}
        rows={5}
        onChange={(event) => onChange(event.target.value)}
      />
    </label>
  )
}

function DetailEmpty({
  title,
  detail,
  action,
  onAction,
}: {
  title: string
  detail: string
  action: string
  onAction: () => void
}) {
  return (
    <div className="flex-1 grid place-items-center p-6 page-in">
      <div className="max-w-md text-center">
        <BookOpen size={24} className="text-fog mx-auto mb-3" />
        <h1 className="text-sm font-semibold text-ink mb-1">{title}</h1>
        <p className="text-xs text-fog leading-relaxed mb-4">{detail}</p>
        <button
          type="button"
          className="btn btn-secondary text-xs"
          onClick={onAction}
        >
          {action}
        </button>
      </div>
    </div>
  )
}

function DecisionDialog({
  kind,
  direction,
  busy,
  error,
  onDirection,
  onClose,
  onConfirm,
}: {
  kind: Exclude<DialogKind, null>
  direction: string
  busy: boolean
  error: string
  onDirection: (value: string) => void
  onClose: () => void
  onConfirm: () => void
}) {
  const cancelling = kind === "cancel"
  return (
    <div
      className="fixed inset-0 z-50 grid place-items-center bg-black/55 backdrop-blur-sm p-4"
      role="presentation"
      onMouseDown={onClose}
    >
      <section
        className="w-full max-w-md bg-surface border border-hairline rounded-lg shadow-2xl p-5"
        role="dialog"
        aria-modal="true"
        aria-labelledby="detail-decision-title"
        onMouseDown={(event) => event.stopPropagation()}
      >
        <h2
          id="detail-decision-title"
          className="text-sm font-semibold text-ink"
        >
          {cancelling ? "取消本次创作 Run" : "定向重做章节施工图"}
        </h2>
        <p className="text-xs text-fog leading-relaxed mt-2">
          {cancelling
            ? "取消会停止当前 Run，不会改写已经定稿的历史 Artifact。"
            : "只填写希望调整的章节节奏、场景职责或跨章交接；卷数和章节槽位仍由冻结合同控制。"}
        </p>
        {!cancelling && (
          <textarea
            className="input text-sm w-full mt-4 min-h-28"
            placeholder="例如：加强第二卷中段的关系推进，避免连续调查场景。"
            value={direction}
            onChange={(event) => onDirection(event.target.value)}
          />
        )}
        {error && (
          <p className="text-xs text-risk mt-3" role="alert">
            {error}
          </p>
        )}
        <div className="flex justify-end gap-2 mt-5">
          <button
            type="button"
            className="btn btn-secondary text-xs"
            disabled={busy}
            onClick={onClose}
          >
            返回
          </button>
          <button
            type="button"
            className={`btn text-xs ${
              cancelling ? "btn-danger" : "btn-primary"
            }`}
            disabled={busy || (!cancelling && !direction.trim())}
            onClick={onConfirm}
          >
            {busy ? "正在提交…" : cancelling ? "确认取消" : "开始换稿"}
          </button>
        </div>
      </section>
    </div>
  )
}
