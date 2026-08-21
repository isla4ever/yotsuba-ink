import { useEffect, useMemo, useState, type ReactNode } from "react"
import {
  AlertTriangle,
  ArrowRight,
  BookOpen,
  CheckCircle2,
  CircleStop,
  DatabaseZap,
  FileText,
  GitCommitHorizontal,
  History,
  ListTree,
  MessageSquare,
  Monitor,
  RefreshCw,
  Save,
  UsersRound,
  X,
} from "lucide-react"
import { useApp } from "../state/PipelineAppProvider"
import {
  parseCharacterBibleArtifact,
  parseChapterArtifact,
  parseDetailArtifact,
  type ChapterArtifact,
  type DetailChapter,
} from "@/features/pipeline/contracts/artifacts"
import { BookLoader } from "@/features/pipeline/layout/BookLoader"
import { useLoadingPresence } from "@/features/pipeline/layout/useLoadingPresence"
import {
  detailChapterProgress,
  orderedNumber,
} from "@/features/pipeline/lib/detailPresentation"
import {
  chapterAuthorStatusLabel,
  chapterVersionsFor,
  nonWhitespaceCharacters,
  selectedChapterVersion,
} from "@/features/pipeline/lib/textPresentation"
import {
  textDecisionFor,
  type TextDecision,
  type TextDecisionAction,
  type TextQualityFinding,
} from "@/features/pipeline/lib/textDecision"
import type { StageDecision } from "@/features/pipeline/lib/stageDecision"
import { resolveRunDecision } from "@/features/pipeline/services/runApi"
import { useStageArtifactDraft } from "@/features/pipeline/state/useStageArtifactDraft"

type InspectorTab = "review" | "blueprint" | "versions"
type DialogKind = "regenerate" | "cancel" | null

export default function TextStageView() {
  const {
    activeProject,
    activeRun,
    refreshRun,
    runArtifactError,
    runArtifactLoading,
    runArtifacts,
    runChapters,
    runLoading,
    selectedChapter,
    setRoute,
    setSelectedChapter,
  } = useApp()
  const detail = useMemo(
    () => parseDetailArtifact(runArtifacts.detail?.payload),
    [runArtifacts.detail],
  )
  const cast = useMemo(
    () => parseCharacterBibleArtifact(runArtifacts.cast?.payload),
    [runArtifacts.cast],
  )
  const pendingTextDecision = useMemo(
    () => textDecisionFor(activeRun),
    [activeRun],
  )
  const artifact = detail.artifact
  const chapter =
    artifact?.chapters.find((item) => item.ref === selectedChapter) ??
    artifact?.chapters[0]
  const chapterId = chapter?.ref ?? ""
  const decision = useMemo(
    () => (chapterId ? textDecisionFor(activeRun, chapterId) : null),
    [activeRun, chapterId],
  )
  const versions = useMemo(
    () => chapterVersionsFor(chapterId, runChapters),
    [chapterId, runChapters],
  )
  const automaticRecord = useMemo(
    () => selectedChapterVersion(chapterId, runChapters, decision),
    [chapterId, decision, runChapters],
  )
  const [selectedVersionId, setSelectedVersionId] = useState("")
  const selectedRecord =
    versions.find((record) => record.version_id === selectedVersionId) ??
    automaticRecord
  const draftDecision = useMemo<StageDecision | null>(() => {
    if (
      !decision ||
      decision.kind !== "author" ||
      !selectedRecord ||
      selectedRecord.version_id !== decision.chapterVersionId
    )
      return null
    return {
      allowedActions: decision.allowedActions.filter(
        (item): item is StageDecision["allowedActions"][number] =>
          item === "accept" || item === "regenerate" || item === "cancel",
      ),
      artifactRef: decision.artifactRef || selectedRecord.version_id,
      decisionId: decision.decisionId,
      domainRevision: decision.domainRevision,
      regenerationLimit: decision.quality?.regenerationLimit ?? 0,
      regenerationUsed: decision.quality?.regenerationUsed ?? 0,
      stageId: "text",
    }
  }, [decision, selectedRecord])
  const draftSource = useMemo(
    () =>
      selectedRecord
        ? {
            artifact_id: selectedRecord.version_id,
            payload: selectedRecord.artifact,
          }
        : undefined,
    [selectedRecord],
  )
  const stageDraft = useStageArtifactDraft(
    activeRun?.definition.run_id ?? "",
    draftDecision,
    draftSource,
  )
  const parsedChapter = useMemo(
    () => parseChapterArtifact(stageDraft.artifact ?? selectedRecord?.artifact),
    [selectedRecord, stageDraft.artifact],
  )
  const [inspectorOpen, setInspectorOpen] = useState(false)
  const [inspectorTab, setInspectorTab] = useState<InspectorTab>("review")
  const [dialog, setDialog] = useState<DialogKind>(null)
  const [direction, setDirection] = useState("")
  const [action, setAction] = useState<TextDecisionAction | "">("")
  const [actionError, setActionError] = useState("")

  useEffect(() => {
    if (!artifact?.chapters.length) return
    if (artifact.chapters.some((item) => item.ref === selectedChapter)) return
    const activeRef = pendingTextDecision?.chapterId
      ? pendingTextDecision.chapterId
      : `chapter-${activeRun?.read_model.active_chapter_number ?? 1}`
    const next =
      artifact.chapters.find((item) => item.ref === activeRef) ??
      artifact.chapters[0]
    setSelectedChapter(next.ref)
  }, [
    activeRun?.read_model.active_chapter_number,
    artifact,
    pendingTextDecision?.chapterId,
    selectedChapter,
    setSelectedChapter,
  ])

  useEffect(() => {
    setSelectedVersionId(automaticRecord?.version_id ?? "")
  }, [automaticRecord?.version_id, chapterId])

  const initialLoad = useLoadingPresence(runLoading || runArtifactLoading)

  if (initialLoad.visible) {
    return (
      <BookLoader
        phase={initialLoad.exiting ? "exit" : "enter"}
        variant="panel"
        label="正在铺开正文稿纸"
        detail="同步章节版本、作者决策与 Evidence 状态"
      />
    )
  }

  if (!activeProject?.latestRunId || !activeRun) {
    return (
      <TextEmpty
        title="当前作品尚未启动创作 Run"
        detail="正文版本由已经定稿的章节施工图逐章生成。"
        action="返回作品库"
        onAction={() => setRoute("studio")}
      />
    )
  }

  if (!artifact || !chapter) {
    return (
      <TextEmpty
        title="正文施工图尚未就绪"
        detail={
          runArtifactError ||
          detail.error ||
          "请先完成 Detail Artifact，再开始正文生产。"
        }
        action="查看细纲"
        onAction={() => setRoute("detail")}
      />
    )
  }

  const castNames = new Map(
    cast.artifact?.subjects.map((subject) => [subject.id, subject.name]) ?? [],
  )
  const displayedIsDecisionTarget = Boolean(
    decision &&
      selectedRecord &&
      selectedRecord.version_id === decision.chapterVersionId,
  )
  const editable = Boolean(
    decision?.kind === "author" &&
      displayedIsDecisionTarget &&
      parsedChapter.artifact,
  )
  const editorContent = parsedChapter.artifact?.content ?? ""
  const editedArtifact = parsedChapter.artifact
  const editedValidation = parseChapterArtifact(editedArtifact)
  const contentChanged = Boolean(
    parsedChapter.artifact && editorContent !== parsedChapter.artifact.content,
  )

  const submitDecision = async (
    targetDecision: TextDecision,
    nextAction: TextDecisionAction,
  ) => {
    if (action || !targetDecision.allowedActions.includes(nextAction)) return
    if (nextAction === "accept" && !editedValidation.artifact) {
      setActionError(
        editedValidation.error || "当前正文未通过 Chapter Artifact 校验",
      )
      return
    }
    if (nextAction === "regenerate" && !direction.trim()) {
      setActionError("请先填写定向换稿要求")
      return
    }
    setAction(nextAction)
    setActionError("")
    try {
      await resolveRunDecision(
        activeRun.definition.run_id,
        targetDecision.decisionId,
        nextAction,
        targetDecision.domainRevision,
        nextAction === "accept"
          ? editedValidation.artifact as unknown as Record<string, unknown>
          : undefined,
        nextAction === "regenerate" ? direction : undefined,
      )
      setDialog(null)
      setDirection("")
      await refreshRun()
    } catch (reason) {
      setActionError(
        reason instanceof Error ? reason.message : "正文决策提交失败",
      )
    } finally {
      setAction("")
    }
  }

  return (
    <div className="flex-1 overflow-hidden flex flex-col page-in">
      <TextStageBar
        activeRun={activeRun}
        chapter={chapter}
        decision={decision}
        pendingTextDecision={pendingTextDecision}
        displayedIsDecisionTarget={displayedIsDecisionTarget}
        editable={editable}
        action={action}
        onAccept={() => decision && void submitDecision(decision, "accept")}
        onCancel={() => setDialog("cancel")}
        onRegenerate={() => setDialog("regenerate")}
        onRetryEvidence={() =>
          decision && void submitDecision(decision, "retry_evidence")
        }
        onPendingChapter={() => {
          if (pendingTextDecision)
            setSelectedChapter(pendingTextDecision.chapterId)
        }}
        onMonitor={() => setRoute("run-monitor")}
      />

      <div className="flex-1 overflow-hidden flex min-h-0 relative">
        <TextChapterRail
          artifact={artifact}
          activeRun={activeRun}
          runChapters={runChapters}
          selectedChapter={chapter.ref}
          onSelect={setSelectedChapter}
        />

        <main className="flex-1 overflow-hidden flex flex-col min-w-0 bg-elev">
          <div className="border-b border-ghost px-4 py-2.5 bg-surface shrink-0">
            <div className="md:hidden mb-2">
              <select
                aria-label="选择正文章节"
                className="input text-xs w-full"
                value={chapter.ref}
                onChange={(event) => setSelectedChapter(event.target.value)}
              >
                {artifact.chapters.map((item) => (
                  <option key={item.ref} value={item.ref}>
                    第 {orderedNumber(item.ref)} 章 · {item.title}
                  </option>
                ))}
              </select>
            </div>
            <div className="flex items-center gap-2 min-w-0">
              <strong className="text-sm text-ink truncate">
                第 {orderedNumber(chapter.ref)} 章 · 《{chapter.title}》
              </strong>
              <span className="text-[10px] text-fog hidden sm:inline">
                {castNames.get(chapter.pov) ?? chapter.pov} 视角
              </span>
              <div className="flex-1" />
              {selectedRecord && (
                <span className="text-[10px] text-fog hidden sm:inline">
                  {chapterAuthorStatusLabel(
                    selectedRecord.artifact.author_status,
                  )}{" "}
                  · {nonWhitespaceCharacters(editorContent).toLocaleString()}{" "}
                  字符
                </span>
              )}
              <button
                type="button"
                aria-label="打开章节检查器"
                className="btn btn-ghost text-xs lg:hidden"
                onClick={() => setInspectorOpen(true)}
              >
                <MessageSquare size={12} /> 检查
              </button>
            </div>
          </div>

          <div className="flex-1 overflow-y-auto">
            <div className="max-w-3xl min-h-full mx-auto px-5 sm:px-8 py-7 sm:py-10">
              {selectedRecord && parsedChapter.artifact ? (
                editable ? (
                  <textarea
                    aria-label="正文编辑器"
                    className="manuscript w-full min-h-[68vh] bg-transparent text-ink outline-none resize-none leading-[1.95]"
                    data-collaboration-field-path="content"
                    data-collaboration-unit={chapter.ref}
                    value={editorContent}
                    onChange={(event) => {
                      if (!parsedChapter.artifact) return
                      stageDraft.change({
                        ...parsedChapter.artifact,
                        content: event.target.value,
                      } as unknown as Record<string, unknown>)
                    }}
                  />
                ) : (
                  <textarea
                    aria-label="正文阅读器"
                    className="manuscript w-full min-h-[68vh] bg-transparent text-ink outline-none resize-none leading-[1.95]"
                    data-collaboration-field-path="content"
                    data-collaboration-unit={chapter.ref}
                    readOnly
                    value={parsedChapter.artifact.content}
                  />
                )
              ) : (
                <div className="min-h-[55vh] grid place-items-center text-center">
                  <div>
                    <FileText size={25} className="text-fog mx-auto mb-3" />
                    <h2 className="text-sm font-semibold text-ink mb-1">
                      本章尚无正文版本
                    </h2>
                    <p className="text-xs text-fog max-w-sm">
                      正文按章顺序生成；当前 Run 仍停在第{" "}
                      {activeRun.read_model.active_chapter_number} 章。
                    </p>
                    <button
                      type="button"
                      className="btn btn-secondary text-xs mt-4"
                      onClick={() => setRoute("run-monitor")}
                    >
                      <Monitor size={12} /> 查看实时监控
                    </button>
                  </div>
                </div>
              )}
            </div>
          </div>

          <footer className="border-t border-hairline bg-surface px-4 py-1.5 flex items-center gap-3 text-[10px] text-fog shrink-0">
            <span>{chapter.volume_ref}</span>
            <span>{chapter.scenes.length} 个场景</span>
            <span>
              预算 {chapter.target_characters?.toLocaleString() ?? "待定"} 字符
            </span>
            {contentChanged && (
              <span className="text-amber">人工编辑尚未定稿</span>
            )}
            <span className="ml-auto truncate max-w-[45%]">
              {selectedRecord?.version_id ?? "等待正文版本"}
            </span>
          </footer>
        </main>

        {inspectorOpen && (
          <button
            type="button"
            className="fixed inset-0 z-30 bg-black/50 lg:hidden"
            aria-label="关闭章节检查器"
            onClick={() => setInspectorOpen(false)}
          />
        )}
        <ChapterInspector
          open={inspectorOpen}
          tab={inspectorTab}
          chapter={chapter}
          decision={decision}
          selectedVersionId={selectedRecord?.version_id ?? ""}
          versions={versions}
          onClose={() => setInspectorOpen(false)}
          onTab={setInspectorTab}
          onVersion={setSelectedVersionId}
        />
      </div>

      {(actionError || stageDraft.error || (editable && !editedValidation.artifact)) && (
        <div
          role="alert"
          className="fixed bottom-12 left-1/2 z-50 -translate-x-1/2 max-w-[90vw] border border-risk/40 bg-surface rounded-lg px-4 py-2 text-xs text-risk shadow-xl"
        >
          {actionError || stageDraft.error || editedValidation.error}
        </div>
      )}

      {dialog && decision && (
        <TextDecisionDialog
          kind={dialog}
          direction={direction}
          busy={Boolean(action)}
          error={actionError}
          recommendation={decision.quality?.recommendation ?? ""}
          onDirection={setDirection}
          onClose={() => {
            if (action) return
            setDialog(null)
            setActionError("")
          }}
          onConfirm={() =>
            void submitDecision(
              decision,
              dialog === "cancel" ? "cancel" : "regenerate",
            )
          }
        />
      )}
    </div>
  )
}

function TextStageBar({
  activeRun,
  chapter,
  decision,
  pendingTextDecision,
  displayedIsDecisionTarget,
  editable,
  action,
  onAccept,
  onCancel,
  onRegenerate,
  onRetryEvidence,
  onPendingChapter,
  onMonitor,
}: {
  activeRun: NonNullable<ReturnType<typeof useApp>["activeRun"]>
  chapter: DetailChapter
  decision: TextDecision | null
  pendingTextDecision: TextDecision | null
  displayedIsDecisionTarget: boolean
  editable: boolean
  action: TextDecisionAction | ""
  onAccept: () => void
  onCancel: () => void
  onRegenerate: () => void
  onRetryEvidence: () => void
  onPendingChapter: () => void
  onMonitor: () => void
}) {
  const evidenceRecovery = decision?.kind === "evidence"
  const pendingElsewhere = pendingTextDecision && !decision
  return (
    <header className="stage-aura border-b border-hairline bg-surface px-4 md:px-6 py-3 flex items-center gap-2 shrink-0">
      <div className="flex items-center gap-2 flex-1 min-w-0">
        {evidenceRecovery ? (
          <AlertTriangle size={14} className="text-amber shrink-0" />
        ) : decision ? (
          <FileText size={14} className="text-action shrink-0" />
        ) : (
          <CheckCircle2 size={14} className="text-mint shrink-0" />
        )}
        <div className="min-w-0">
          <strong className="block text-xs text-ink">
            {evidenceRecovery
              ? "正文已接受，Evidence 需要处理"
              : decision
                ? "章节候选等待作者定稿"
                : "正文版本只读查看"}
          </strong>
          <span className="block text-[10px] text-fog truncate">
            第 {orderedNumber(chapter.ref)} 章 ·{" "}
            {activeRun.read_model.status === "awaiting_decision"
              ? "Run 等待决策"
              : "Run 同步中"}
          </span>
        </div>
      </div>
      {pendingElsewhere ? (
        <button
          type="button"
          className="btn btn-primary text-xs"
          onClick={onPendingChapter}
        >
          回到待处理章节 <ArrowRight size={12} />
        </button>
      ) : evidenceRecovery && displayedIsDecisionTarget ? (
        <>
          <button
            type="button"
            className="btn btn-secondary text-xs"
            disabled={Boolean(action)}
            onClick={onRetryEvidence}
          >
            <DatabaseZap size={12} />{" "}
            {action === "retry_evidence" ? "重试中…" : "重试证据提取"}
          </button>
          <button
            type="button"
            className="btn btn-ghost text-risk text-xs hidden sm:inline-flex"
            disabled={Boolean(action)}
            onClick={onCancel}
          >
            <CircleStop size={12} /> 取消 Run
          </button>
        </>
      ) : decision?.kind === "author" && displayedIsDecisionTarget ? (
        <>
          {decision.allowedActions.includes("regenerate") && (
            <button
              type="button"
              className="btn btn-secondary text-xs hidden sm:inline-flex"
              disabled={Boolean(action)}
              onClick={onRegenerate}
            >
              <RefreshCw size={12} /> 定向换稿
            </button>
          )}
          {decision.allowedActions.includes("cancel") && (
            <button
              type="button"
              className="btn btn-ghost text-risk text-xs hidden sm:inline-flex"
              disabled={Boolean(action)}
              onClick={onCancel}
            >
              <CircleStop size={12} /> 取消
            </button>
          )}
          <button
            type="button"
            className="btn btn-primary text-xs"
            disabled={!editable || Boolean(action)}
            onClick={onAccept}
          >
            <Save size={12} />{" "}
            {action === "accept" ? "定稿中…" : "确认正文定稿"}
          </button>
        </>
      ) : (
        <button
          type="button"
          className="btn btn-secondary text-xs"
          onClick={onMonitor}
        >
          <Monitor size={12} /> 实时监控
        </button>
      )}
    </header>
  )
}

function TextChapterRail({
  artifact,
  activeRun,
  runChapters,
  selectedChapter,
  onSelect,
}: {
  artifact: NonNullable<ReturnType<typeof parseDetailArtifact>["artifact"]>
  activeRun: NonNullable<ReturnType<typeof useApp>["activeRun"]>
  runChapters: ReturnType<typeof useApp>["runChapters"]
  selectedChapter: string
  onSelect: (chapterId: string) => void
}) {
  return (
    <aside
      className="hidden md:flex flex-col w-52 border-r border-hairline bg-surface overflow-hidden shrink-0"
      aria-label="正文章节导航"
    >
      <div className="px-3 py-2 border-b border-ghost text-[10px] text-fog uppercase">
        正文生产 · {artifact.chapters.length} 章
      </div>
      <nav className="flex-1 overflow-y-auto p-2 space-y-0.5">
        {artifact.chapters.map((chapter, index) => {
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
                className={`w-full text-left px-3 py-2.5 rounded-lg border transition-colors ${
                  chapter.ref === selectedChapter
                    ? "bg-elev border-hairline"
                    : "border-transparent hover:bg-hover"
                }`}
                onClick={() => onSelect(chapter.ref)}
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
              </button>
            </div>
          )
        })}
      </nav>
    </aside>
  )
}

function ChapterInspector({
  open,
  tab,
  chapter,
  decision,
  selectedVersionId,
  versions,
  onClose,
  onTab,
  onVersion,
}: {
  open: boolean
  tab: InspectorTab
  chapter: DetailChapter
  decision: TextDecision | null
  selectedVersionId: string
  versions: ReturnType<typeof chapterVersionsFor>
  onClose: () => void
  onTab: (tab: InspectorTab) => void
  onVersion: (versionId: string) => void
}) {
  return (
    <aside
      className={`${
        open ? "flex" : "hidden"
      } fixed inset-y-0 right-0 z-40 w-[min(86vw,320px)] lg:static lg:z-auto lg:flex lg:w-72 border-l border-hairline bg-surface flex-col shrink-0 shadow-2xl lg:shadow-none`}
      aria-label="章节检查器"
    >
      <div className="flex items-center border-b border-hairline shrink-0">
        {(["review", "blueprint", "versions"] as InspectorTab[]).map((item) => (
          <button
            key={item}
            type="button"
            className={`flex-1 py-2.5 text-xs transition-colors ${
              tab === item
                ? "text-ink border-b-2 border-mint"
                : "text-fog hover:text-ink"
            }`}
            onClick={() => onTab(item)}
          >
            {item === "review"
              ? "审校"
              : item === "blueprint"
                ? "蓝图"
                : "版本"}
          </button>
        ))}
        <button
          type="button"
          className="btn btn-ghost p-2 lg:hidden"
          aria-label="关闭检查器"
          onClick={onClose}
        >
          <X size={14} />
        </button>
      </div>
      <div className="flex-1 overflow-y-auto p-3">
        {tab === "review" && <ReviewInspector decision={decision} />}
        {tab === "blueprint" && <BlueprintInspector chapter={chapter} />}
        {tab === "versions" && (
          <div className="space-y-2">
            <p className="text-[10px] text-fog uppercase mb-3">
              不可变章节版本
            </p>
            {versions.length ? (
              versions.map((record) => (
                <button
                  key={record.version_id}
                  type="button"
                  className={`w-full text-left border rounded-lg p-3 transition-colors ${
                    record.version_id === selectedVersionId
                      ? "border-mint/50 bg-mint-bg"
                      : "border-hairline bg-elev hover:bg-hover"
                  }`}
                  onClick={() => onVersion(record.version_id)}
                >
                  <div className="flex items-center gap-2">
                    <History size={11} className="text-action" />
                    <strong className="text-xs text-ink truncate">
                      {chapterAuthorStatusLabel(record.artifact.author_status)}
                    </strong>
                  </div>
                  <span className="block text-[10px] text-fog mt-1 break-all">
                    {record.version_id}
                  </span>
                  <span className="block text-[10px] text-fog mt-1">
                    {nonWhitespaceCharacters(
                      record.artifact.content,
                    ).toLocaleString()}{" "}
                    字符
                  </span>
                </button>
              ))
            ) : (
              <InspectorEmpty text="本章还没有正文版本。" />
            )}
          </div>
        )}
      </div>
    </aside>
  )
}

function ReviewInspector({ decision }: { decision: TextDecision | null }) {
  const quality = decision?.quality
  if (!decision)
    return (
      <InspectorEmpty text="本章没有待处理的作者决策。已接受版本可安全只读查看。" />
    )
  if (!quality)
    return (
      <InspectorEmpty text="该历史决策没有新版质量投影；界面不会伪造评分或审校意见。" />
    )
  const findings = [...quality.blockers, ...quality.warnings]
  return (
    <div className="space-y-3">
      <div className="bg-elev border border-hairline rounded-lg p-3">
        <div className="grid grid-cols-2 gap-3 text-xs">
          <InspectorMetric
            label="结构合同"
            value={quality.structureContract === "passed" ? "通过" : "阻断"}
            tone={
              quality.structureContract === "passed" ? "text-mint" : "text-risk"
            }
          />
          <InspectorMetric
            label="Evidence"
            value={
              quality.evidenceStatus === "needs_action"
                ? "需要处理"
                : quality.evidenceStatus === "succeeded"
                  ? "已完成"
                  : "等待正文接受"
            }
            tone={quality.evidenceDegraded ? "text-amber" : "text-mint"}
          />
          <InspectorMetric
            label="审稿告警"
            value={`${quality.warnings.length} 项`}
          />
          <InspectorMetric
            label="换稿额度"
            value={`${quality.regenerationUsed}/${quality.regenerationLimit}`}
          />
        </div>
      </div>
      {decision.kind === "evidence" && (
        <div className="border border-amber/35 bg-amber-bg rounded-lg p-3">
          <strong className="text-xs text-amber">
            只重试 Evidence，不重写正文
          </strong>
          <p className="text-[10px] text-fog leading-relaxed mt-1">
            正文版本已经接受；本次恢复只修复证据提取与后续写回。
          </p>
        </div>
      )}
      {findings.length ? (
        findings.map((finding, index) => (
          <FindingCard
            key={`${finding.code}-${index}`}
            finding={finding}
            blocking={index < quality.blockers.length}
          />
        ))
      ) : (
        <InspectorEmpty text="当前质量合同没有阻断项或审校告警。" />
      )}
    </div>
  )
}

function BlueprintInspector({ chapter }: { chapter: DetailChapter }) {
  return (
    <div className="space-y-3">
      <InspectorSection
        icon={<ListTree size={11} />}
        label="章节目的"
        text={chapter.purpose}
      />
      {chapter.scenes.map((scene, index) => (
        <div
          key={`${chapter.ref}-blueprint-${index}`}
          className="bg-elev border border-hairline rounded-lg p-3"
        >
          <strong className="text-xs text-ink">
            场景 {index + 1} · {scene.place}
          </strong>
          <dl className="mt-2 space-y-2 text-[10px]">
            <BlueprintRow label="目标" value={scene.objective} />
            <BlueprintRow label="冲突" value={scene.conflict} />
            <BlueprintRow label="转折" value={scene.turn} />
            <BlueprintRow label="结果" value={scene.result} />
          </dl>
        </div>
      ))}
      <InspectorSection
        icon={<GitCommitHorizontal size={11} />}
        label="跨章交接"
        text={chapter.handoff}
      />
    </div>
  )
}

function FindingCard({
  finding,
  blocking,
}: {
  finding: TextQualityFinding
  blocking: boolean
}) {
  return (
    <article className="bg-elev border border-hairline rounded-lg p-3">
      <div
        className={`flex items-center gap-1.5 text-[10px] ${
          blocking ? "text-risk" : "text-amber"
        }`}
      >
        <AlertTriangle size={10} /> {blocking ? "合同阻断" : "审校告警"} ·{" "}
        {finding.code || "未分类"}
      </div>
      <strong className="block text-xs text-ink mt-2">
        {finding.claim || "未提供判断摘要"}
      </strong>
      {finding.evidence && (
        <p className="text-[10px] text-fog leading-relaxed mt-1">
          证据：{finding.evidence}
        </p>
      )}
    </article>
  )
}

function InspectorMetric({
  label,
  value,
  tone = "text-ink",
}: {
  label: string
  value: string
  tone?: string
}) {
  return (
    <div>
      <span className="block text-[10px] text-fog">{label}</span>
      <strong className={tone}>{value}</strong>
    </div>
  )
}

function InspectorSection({
  icon,
  label,
  text,
}: {
  icon: ReactNode
  label: string
  text: string
}) {
  return (
    <section className="bg-elev border border-hairline rounded-lg p-3">
      <span className="flex items-center gap-1.5 text-[10px] text-action">
        {icon}
        {label}
      </span>
      <p className="text-xs text-ash leading-relaxed mt-2">{text}</p>
    </section>
  )
}

function BlueprintRow({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <dt className="text-fog">{label}</dt>
      <dd className="text-ash leading-relaxed mt-0.5">{value}</dd>
    </div>
  )
}

function InspectorEmpty({ text }: { text: string }) {
  return (
    <div className="py-12 text-center">
      <BookOpen size={20} className="text-fog mx-auto mb-2" />
      <p className="text-xs text-fog leading-relaxed">{text}</p>
    </div>
  )
}

function TextEmpty({
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
        <FileText size={24} className="text-fog mx-auto mb-3" />
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

function TextDecisionDialog({
  kind,
  direction,
  busy,
  error,
  recommendation,
  onDirection,
  onClose,
  onConfirm,
}: {
  kind: Exclude<DialogKind, null>
  direction: string
  busy: boolean
  error: string
  recommendation: string
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
        aria-labelledby="text-decision-title"
        onMouseDown={(event) => event.stopPropagation()}
      >
        <h2 id="text-decision-title" className="text-sm font-semibold text-ink">
          {cancelling ? "取消本次创作 Run" : "定向重写当前章节"}
        </h2>
        <p className="text-xs text-fog leading-relaxed mt-2">
          {cancelling
            ? "取消只终止当前 Run，不删除已有不可变章节版本。"
            : "系统只允许一次定向换稿，并继续使用冻结施工图与上下文。"}
        </p>
        {!cancelling && (
          <textarea
            className="input text-sm w-full mt-4 min-h-28"
            placeholder={
              recommendation || "例如：压缩解释段落，把信息藏进行动和对话。"
            }
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
