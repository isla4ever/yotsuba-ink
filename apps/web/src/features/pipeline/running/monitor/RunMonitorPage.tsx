import { useEffect, useMemo, useRef, useState, type ReactNode } from "react"
import {
  Activity,
  AlertTriangle,
  BookOpen,
  Bot,
  CheckCircle2,
  ChevronRight,
  CircleDot,
  FileText,
  Layers,
  ListTree,
  PanelRightOpen,
  RefreshCw,
  ScrollText,
  Users,
  X,
} from "lucide-react"
import { useApp } from "../../state/PipelineAppProvider"
import type {
  ChapterVersionRecord,
  GraphStageStatus,
  NarrativeStageId,
  RunArtifactRecord,
  RunEvent,
} from "@/features/pipeline/contracts/run"
import { BookLoader } from "@/features/pipeline/layout/BookLoader"
import { useLoadingPresence } from "@/features/pipeline/layout/useLoadingPresence"
import { projectLiveRun } from "@/features/pipeline/lib/liveRunProjection"

const STAGES: Array<{
  id: NarrativeStageId
  label: string
  icon: ReactNode
}> = [
  { id: "brief", label: "简报", icon: <FileText size={13} /> },
  { id: "spine", label: "脊柱", icon: <Layers size={13} /> },
  { id: "cast", label: "角色", icon: <Users size={13} /> },
  { id: "volumes", label: "卷册", icon: <BookOpen size={13} /> },
  { id: "detail", label: "细纲", icon: <ListTree size={13} /> },
  { id: "text", label: "正文", icon: <ScrollText size={13} /> },
  { id: "cover", label: "封面", icon: <CircleDot size={13} /> },
  { id: "export", label: "导出", icon: <CheckCircle2 size={13} /> },
]

const STATUS_LABELS: Record<string, string> = {
  created: "待启动",
  running: "运行中",
  awaiting_decision: "等待决策",
  completed: "已完成",
  failed: "失败",
  cancelled: "已取消",
  locked: "未解锁",
  available: "可执行",
}

export default function RunMonitorPage() {
  const {
    activeProject,
    activeRun,
    acceptedRunChapters,
    refreshRun,
    runConnection,
    runError,
    runEvents,
    runArtifactError,
    runArtifactLoading,
    runArtifacts,
    runLoading,
    setRoute,
  } = useApp()
  const acceptedChapters = acceptedRunChapters
  const artifacts = runArtifacts
  const liveRun = useMemo(
    () => projectLiveRun(activeRun, runEvents),
    [activeRun, runEvents],
  )
  const [selectedStage, setSelectedStage] = useState<NarrativeStageId>("brief")
  const [selectedChapterId, setSelectedChapterId] = useState("")
  const [inspectorOpen, setInspectorOpen] = useState(false)
  const initializedRunId = useRef("")
  const stageFollowRef = useRef(true)
  const previousActiveStage = useRef<NarrativeStageId | "">("")

  useEffect(() => {
    const runId = activeRun?.definition.run_id ?? ""
    if (!runId || initializedRunId.current === runId) return
    initializedRunId.current = runId
    stageFollowRef.current = true
    setSelectedStage(liveRun?.read_model.active_stage_id ?? "brief")
    setSelectedChapterId("")
  }, [liveRun])

  useEffect(() => {
    const activeStage = liveRun?.read_model.active_stage_id
    if (!activeStage) return
    if (
      stageFollowRef.current ||
      selectedStage === previousActiveStage.current
    ) {
      setSelectedStage(activeStage)
    }
    previousActiveStage.current = activeStage
  }, [liveRun?.read_model.active_stage_id, selectedStage])

  useEffect(() => {
    if (selectedChapterId || acceptedChapters.length === 0) return
    const activeChapterId = `chapter-${liveRun?.read_model.active_chapter_number ?? 0}`
    const selected =
      acceptedChapters.find(
        (chapter) => chapter.chapter_id === activeChapterId,
      ) ?? acceptedChapters[acceptedChapters.length - 1]
    setSelectedChapterId(selected.chapter_id)
  }, [
    acceptedChapters,
    liveRun?.read_model.active_chapter_number,
    selectedChapterId,
  ])

  const selectedChapter = useMemo(
    () =>
      acceptedChapters.find(
        (chapter) => chapter.chapter_id === selectedChapterId,
      ) ??
      acceptedChapters[0] ??
      null,
    [acceptedChapters, selectedChapterId],
  )

  if (!activeProject?.latestRunId) {
    return (
      <div className="flex-1 grid place-items-center p-6 page-in">
        <div className="bg-surface border border-hairline rounded-lg p-6 max-w-md text-center">
          <Activity size={22} className="text-fog mx-auto mb-3" />
          <h1 className="text-sm font-semibold text-ink mb-1">
            当前作品尚未创建 Run
          </h1>
          <p className="text-xs text-fog mb-4">
            完成运行前配置并启动后，实时内容、健康状态、决策与日志会在这里同步。
          </p>
          <button
            type="button"
            className="btn btn-primary text-xs"
            onClick={() => setRoute("brief")}
          >
            返回创作工作台
          </button>
        </div>
      </div>
    )
  }

  return (
    <div className="flex-1 min-h-0 overflow-hidden flex flex-col bg-base page-in">
      <header className="h-12 px-4 border-b border-hairline bg-surface flex items-center gap-3 shrink-0">
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2">
            <h1 className="text-sm font-semibold text-ink truncate">
              实时监控控制台
            </h1>
            <span
              className={`w-1.5 h-1.5 rounded-full ${
                activeRun?.read_model.status === "running"
                  ? "bg-action status-quiet"
                  : "bg-fog"
              }`}
            />
          </div>
          <div className="text-[10px] text-fog truncate font-mono">
            {activeRun?.definition.run_id ?? activeProject.latestRunId}
          </div>
        </div>

        <select
          className="input text-xs py-1.5 w-28 lg:hidden"
          value={selectedStage}
          onChange={(event) => {
            stageFollowRef.current = false
            setSelectedStage(event.target.value as NarrativeStageId)
          }}
          aria-label="监控阶段"
        >
          {STAGES.map((stage) => (
            <option key={stage.id} value={stage.id}>
              {stage.label}
            </option>
          ))}
        </select>
        <button
          type="button"
          className="btn btn-ghost text-xs"
          onClick={() => void refreshRun()}
          title="刷新 Run 状态"
        >
          <RefreshCw size={12} />
          刷新
        </button>
        <button
          type="button"
          className="btn btn-secondary text-xs xl:hidden"
          onClick={() => setInspectorOpen(true)}
        >
          <PanelRightOpen size={12} />
          健康与日志
        </button>
        <button
          type="button"
          className="btn btn-primary text-xs"
          onClick={() => setRoute(selectedStage)}
        >
          前往工作台 <ChevronRight size={12} />
        </button>
      </header>

      {(runError || runArtifactError) && (
        <div className="mx-4 mt-3 banner-warning" role="alert">
          {runError || runArtifactError}
        </div>
      )}

      <div className="flex flex-1 min-h-0 overflow-hidden">
        <MonitorRail
          acceptedChapters={acceptedChapters}
          activeStage={liveRun?.read_model.active_stage_id ?? "brief"}
          selectedChapterId={selectedChapterId}
          selectedStage={selectedStage}
          stageStatus={liveRun?.read_model.stage_status}
          onSelectChapter={setSelectedChapterId}
          onSelectStage={(stage) => {
            stageFollowRef.current = false
            setSelectedStage(stage)
          }}
        />

        <main className="flex-1 min-w-0 min-h-0 overflow-y-auto p-4 lg:p-5">
          <StageContent
            artifact={artifacts[selectedStage]}
            chapter={selectedChapter}
            loading={runLoading || runArtifactLoading}
            selectedStage={selectedStage}
            stageStatus={liveRun?.read_model.stage_status[selectedStage]}
          />
        </main>

        <MonitorInspector
          className="hidden xl:flex w-80"
          activeRun={liveRun}
          connection={runConnection}
          events={runEvents}
        />
      </div>

      {inspectorOpen && (
        <div className="fixed inset-0 z-50 flex justify-end xl:hidden">
          <button
            type="button"
            className="absolute inset-0 bg-black/50"
            onClick={() => setInspectorOpen(false)}
            aria-label="关闭监控详情"
          />
          <div className="relative w-[min(360px,92vw)] h-full bg-surface border-l border-hairline shadow-2xl flex flex-col animate-slide-right">
            <div className="h-12 border-b border-hairline px-4 flex items-center justify-between shrink-0">
              <span className="text-sm font-medium text-ink">
                运行健康与日志
              </span>
              <button
                type="button"
                className="btn btn-ghost p-1.5"
                onClick={() => setInspectorOpen(false)}
                aria-label="关闭"
              >
                <X size={14} />
              </button>
            </div>
            <MonitorInspector
              className="flex flex-1"
              activeRun={liveRun}
              connection={runConnection}
              events={runEvents}
            />
          </div>
        </div>
      )}
    </div>
  )
}

function MonitorRail({
  acceptedChapters,
  activeStage,
  selectedChapterId,
  selectedStage,
  stageStatus,
  onSelectChapter,
  onSelectStage,
}: {
  acceptedChapters: ChapterVersionRecord[]
  activeStage: NarrativeStageId
  selectedChapterId: string
  selectedStage: NarrativeStageId
  stageStatus?: Record<NarrativeStageId, GraphStageStatus>
  onSelectChapter: (chapterId: string) => void
  onSelectStage: (stageId: NarrativeStageId) => void
}) {
  return (
    <aside className="hidden lg:flex w-60 shrink-0 border-r border-hairline bg-surface flex-col min-h-0">
      <div className="p-3 border-b border-ghost">
        <div className="text-[10px] text-fog uppercase tracking-wider mb-2">
          阶段与产物
        </div>
        <div className="space-y-0.5">
          {STAGES.map((stage, index) => {
            const status = stageStatus?.[stage.id] ?? "locked"
            const selected = selectedStage === stage.id
            return (
              <button
                type="button"
                key={stage.id}
                onClick={() => onSelectStage(stage.id)}
                className={`w-full flex items-center gap-2 px-2 py-2 rounded-md text-xs transition-colors ${
                  selected
                    ? "bg-action-bg border border-action/30 text-ink"
                    : "border border-transparent text-fog hover:bg-hover hover:text-ash"
                }`}
              >
                <span className="font-mono text-[10.5px] w-4">{index + 1}</span>
                <span className={selected ? "text-action" : ""}>
                  {stage.icon}
                </span>
                <span className="flex-1 text-left">{stage.label}</span>
                {stage.id === activeStage && (
                  <span className="w-1.5 h-1.5 rounded-full bg-action" />
                )}
                {status === "completed" && (
                  <CheckCircle2 size={10} className="text-mint" />
                )}
                {status === "failed" && (
                  <AlertTriangle size={10} className="text-risk" />
                )}
              </button>
            )
          })}
        </div>
      </div>

      {(selectedStage === "detail" || selectedStage === "text") && (
        <div className="flex-1 min-h-0 overflow-y-auto p-3">
          <div className="text-[10px] text-fog uppercase tracking-wider mb-2">
            已接受章节
          </div>
          {acceptedChapters.length === 0 ? (
            <div className="text-xs text-fog py-3">暂无已接受章节</div>
          ) : (
            acceptedChapters.map((chapter) => (
              <button
                type="button"
                key={chapter.version_id}
                onClick={() => onSelectChapter(chapter.chapter_id)}
                className={`w-full text-left px-2 py-2 rounded-md border mb-1 transition-colors ${
                  selectedChapterId === chapter.chapter_id
                    ? "border-action/30 bg-action-bg"
                    : "border-transparent hover:bg-hover"
                }`}
              >
                <div className="text-[10px] font-mono text-fog">
                  {chapter.chapter_id.replace("chapter-", "CH")}
                </div>
                <div className="text-xs text-ink truncate">
                  {chapter.artifact.title}
                </div>
              </button>
            ))
          )}
        </div>
      )}
    </aside>
  )
}

function StageContent({
  artifact,
  chapter,
  loading,
  selectedStage,
  stageStatus,
}: {
  artifact?: RunArtifactRecord
  chapter: ChapterVersionRecord | null
  loading: boolean
  selectedStage: NarrativeStageId
  stageStatus?: GraphStageStatus
}) {
  const contentLoad = useLoadingPresence(loading && !artifact && !chapter)

  if (contentLoad.visible) {
    return (
      <BookLoader
        phase={contentLoad.exiting ? "exit" : "enter"}
        variant="compact"
        label="正在同步阶段内容"
        detail="实时监控保持无感刷新"
      />
    )
  }
  if (selectedStage === "text") return <TextContent chapter={chapter} />
  if (!artifact) {
    return (
      <div className="h-full min-h-80 grid place-items-center">
        <div className="text-center max-w-sm">
          <CircleDot size={20} className="text-fog mx-auto mb-2" />
          <h2 className="text-sm font-medium text-ink mb-1">
            {STAGES.find((stage) => stage.id === selectedStage)?.label}
            尚无已提交产物
          </h2>
          <p className="text-xs text-fog">
            当前状态：{STATUS_LABELS[stageStatus ?? "locked"] ?? stageStatus}
          </p>
        </div>
      </div>
    )
  }

  const payload = artifact.payload
  if (selectedStage === "brief") return <BriefContent payload={payload} />
  if (selectedStage === "spine") return <SpineContent payload={payload} />
  if (selectedStage === "cast") return <CastContent payload={payload} />
  if (selectedStage === "volumes") return <VolumesContent payload={payload} />
  if (selectedStage === "detail")
    return (
      <DetailContent payload={payload} chapterId={chapter?.chapter_id ?? ""} />
    )
  if (selectedStage === "cover") return <CoverContent payload={payload} />
  return <ExportContent payload={payload} />
}

function ContentHeader({
  eyebrow,
  title,
  children,
}: {
  eyebrow: string
  title: string
  children?: ReactNode
}) {
  return (
    <div className="mb-5 pb-4 border-b border-ghost">
      <div className="text-[10px] text-action uppercase tracking-wider mb-1">
        {eyebrow}
      </div>
      <h2 className="text-lg font-serif font-semibold text-ink">{title}</h2>
      {children}
    </div>
  )
}

function BriefContent({ payload }: { payload: Record<string, unknown> }) {
  return (
    <article className="max-w-4xl mx-auto">
      <ContentHeader
        eyebrow="Story Brief · 已提交"
        title={text(payload.title, "待定书名")}
      />
      <div className="grid md:grid-cols-2 gap-4">
        <TextPanel title="故事前提" value={text(payload.premise)} wide />
        <TextPanel title="读者承诺" value={text(payload.promise)} wide />
        <TextPanel title="主题问题" value={text(payload.theme)} />
        <TextPanel title="结局承诺" value={text(payload.ending_promise)} />
        <TextPanel title="叙事声音" value={text(payload.voice)} wide />
        <ListPanel title="世界规则" items={strings(payload.world_rules)} wide />
      </div>
    </article>
  )
}

function SpineContent({ payload }: { payload: Record<string, unknown> }) {
  const turns = records(payload.turns)
  return (
    <article className="max-w-5xl mx-auto">
      <ContentHeader
        eyebrow="Story Spine · 已提交"
        title={`${turns.length} 个因果推进节点`}
      >
        <p className="text-xs text-fog mt-1">
          因果链按顺序监控；编辑与决策仍在脊柱工作台完成。
        </p>
      </ContentHeader>
      <div className="relative pl-5 space-y-3 before:absolute before:left-[7px] before:top-2 before:bottom-2 before:w-px before:bg-hairline">
        {turns.map((turn, index) => (
          <section
            key={text(turn.id, String(index))}
            className="relative bg-surface border border-hairline rounded-lg p-4"
          >
            <span className="absolute -left-[18px] top-5 w-2 h-2 rounded-full bg-action border-2 border-base" />
            <div className="flex items-center gap-2 mb-2">
              <span className="font-mono text-[10px] text-action">
                TURN {String(index + 1).padStart(2, "0")}
              </span>
              <span className="badge badge-ash">
                {text(turn.progress_type, "推进")}
              </span>
            </div>
            <p className="text-sm text-ink leading-relaxed mb-2">
              <span className="text-fog">因：</span>
              {text(turn.cause)}
            </p>
            <p className="text-sm text-ink leading-relaxed">
              <span className="text-fog">变：</span>
              {text(turn.change)}
            </p>
          </section>
        ))}
      </div>
    </article>
  )
}

function CastContent({ payload }: { payload: Record<string, unknown> }) {
  const subjects = records(payload.subjects)
  return (
    <article className="max-w-5xl mx-auto">
      <ContentHeader
        eyebrow="Character Bible · 已提交"
        title={`${subjects.length} 位冻结主体`}
      />
      <div className="grid md:grid-cols-2 2xl:grid-cols-3 gap-3">
        {subjects.map((subject) => (
          <section
            key={text(subject.id)}
            className="bg-surface border border-hairline rounded-lg p-4"
          >
            <div className="flex items-center gap-2 mb-2">
              <h3 className="text-sm font-semibold text-ink">
                {text(subject.name, "未命名主体")}
              </h3>
              <span className="badge badge-ash">{text(subject.kind)}</span>
            </div>
            <p className="text-xs text-ash leading-relaxed mb-3">
              {text(subject.function)}
            </p>
            <div className="text-[10px] text-fog mb-1">当前利害</div>
            <p className="text-xs text-ink leading-relaxed">
              {text(subject.present_stakes)}
            </p>
          </section>
        ))}
      </div>
    </article>
  )
}

function VolumesContent({ payload }: { payload: Record<string, unknown> }) {
  const volumes = records(payload.volumes)
  return (
    <article className="max-w-5xl mx-auto">
      <ContentHeader
        eyebrow="Volume Architecture · 已提交"
        title={`${volumes.length} 卷自然边界`}
      />
      <div className="space-y-3">
        {volumes.map((volume, index) => (
          <section
            key={text(volume.id, String(index))}
            className="bg-surface border border-hairline rounded-lg p-4"
          >
            <div className="flex items-center gap-3 mb-3">
              <span className="font-mono text-[10px] text-action">
                VOL {String(index + 1).padStart(2, "0")}
              </span>
              <h3 className="text-sm font-semibold text-ink">
                {text(volume.title, `第${index + 1}卷`)}
              </h3>
              <span className="text-[10px] text-fog ml-auto">
                {strings(volume.turn_refs).length} turns
              </span>
            </div>
            <div className="grid md:grid-cols-2 gap-3">
              <TextPanel title="本卷承诺" value={text(volume.promise)} />
              <TextPanel title="核心冲突" value={text(volume.conflict)} />
              <TextPanel title="高潮" value={text(volume.climax)} />
              <TextPanel title="收束" value={text(volume.closure)} />
            </div>
          </section>
        ))}
      </div>
    </article>
  )
}

function DetailContent({
  payload,
  chapterId,
}: {
  payload: Record<string, unknown>
  chapterId: string
}) {
  const chapters = records(payload.chapters)
  const chapter =
    chapters.find((item) => text(item.ref) === chapterId) ?? chapters[0]
  if (!chapter)
    return <div className="text-sm text-fog">细纲产物中没有章节。</div>
  const scenes = records(chapter.scenes)
  return (
    <article className="max-w-5xl mx-auto">
      <ContentHeader
        eyebrow={`${text(chapter.ref).toUpperCase()} · 章节施工图`}
        title={text(chapter.title, "未命名章节")}
      >
        <p className="text-xs text-fog mt-1">{text(chapter.purpose)}</p>
      </ContentHeader>
      <div className="space-y-3">
        {scenes.map((scene, index) => (
          <section
            key={index}
            className="bg-surface border border-hairline rounded-lg p-4"
          >
            <div className="flex items-center gap-2 mb-3">
              <span className="font-mono text-[10px] text-action">
                SCENE {index + 1}
              </span>
              <span className="text-xs text-ink">{text(scene.place)}</span>
            </div>
            <div className="grid md:grid-cols-2 gap-3 text-xs">
              <TextPanel title="目标" value={text(scene.objective)} />
              <TextPanel title="冲突" value={text(scene.conflict)} />
              <TextPanel title="转折" value={text(scene.turn)} />
              <TextPanel title="结果" value={text(scene.result)} />
            </div>
          </section>
        ))}
      </div>
      <div className="mt-4 border border-action/20 bg-action-bg rounded-lg p-4">
        <div className="text-[10px] text-action mb-1">跨章交接</div>
        <p className="text-xs text-ink leading-relaxed">
          {text(chapter.handoff)}
        </p>
      </div>
    </article>
  )
}

function TextContent({ chapter }: { chapter: ChapterVersionRecord | null }) {
  if (!chapter)
    return (
      <div className="h-full grid place-items-center text-sm text-fog">
        暂无已接受正文版本
      </div>
    )
  return (
    <article className="max-w-3xl mx-auto bg-surface border border-hairline rounded-lg px-6 md:px-10 py-8 min-h-full">
      <ContentHeader
        eyebrow={`${chapter.chapter_id.toUpperCase()} · ${chapter.version_id}`}
        title={chapter.artifact.title}
      >
        <p className="text-[10px] text-mint mt-1">作者已接受 · 只读监控投影</p>
      </ContentHeader>
      <div className="whitespace-pre-wrap font-serif text-[15px] text-ink leading-[2]">
        {chapter.artifact.content}
      </div>
    </article>
  )
}

function CoverContent({ payload }: { payload: Record<string, unknown> }) {
  return (
    <article className="max-w-4xl mx-auto">
      <ContentHeader
        eyebrow="Cover Artifact · 已提交"
        title={text(payload.title, "封面制作")}
      />
      <div className="grid md:grid-cols-2 gap-4">
        <TextPanel title="视觉 Brief" value={text(payload.brief)} wide />
        <TextPanel title="图片提示词" value={text(payload.prompt)} wide />
        <ListPanel
          title="视觉关键词"
          items={strings(payload.visual_keywords)}
        />
        <ListPanel title="文案建议" items={strings(payload.copy_suggestions)} />
      </div>
    </article>
  )
}

function ExportContent({ payload }: { payload: Record<string, unknown> }) {
  const files = records(payload.files)
  return (
    <article className="max-w-4xl mx-auto">
      <ContentHeader eyebrow="Export Artifact · 已提交" title="导出清单" />
      <div className="bg-surface border border-hairline rounded-lg divide-y divide-ghost">
        {files.length ? (
          files.map((file, index) => (
            <div
              key={text(file.id, String(index))}
              className="px-4 py-3 flex items-center gap-3"
            >
              <FileText size={13} className="text-fog" />
              <span className="text-sm text-ink flex-1">
                {text(file.name, text(file.path, `文件 ${index + 1}`))}
              </span>
              <span className="badge badge-mint">
                {text(file.status, "ready")}
              </span>
            </div>
          ))
        ) : (
          <div className="px-4 py-5 text-sm text-fog">
            导出产物已提交，当前合同未投影文件清单。
          </div>
        )}
      </div>
    </article>
  )
}

function MonitorInspector({
  activeRun,
  connection,
  events,
  className,
}: {
  activeRun: ReturnType<typeof useApp>["activeRun"]
  connection: ReturnType<typeof useApp>["runConnection"]
  events: RunEvent[]
  className: string
}) {
  const readModel = activeRun?.read_model
  const usage = readModel?.provider_usage
  const recentEvents = events.slice(-120).reverse()
  const connectionPresentation =
    readModel?.status === "awaiting_decision"
      ? { tone: "badge-amber", label: "等待决策" }
      : {
          tone:
            connection === "live"
              ? "badge-mint"
              : connection === "reconnecting"
                ? "badge-amber"
                : "badge-ash",
          label: connectionLabel(connection),
        }
  return (
    <aside
      className={`${className} shrink-0 border-l border-hairline bg-surface flex-col min-h-0 overflow-hidden`}
    >
      <div className="p-4 border-b border-ghost shrink-0">
        <div className="flex items-center justify-between mb-3">
          <span className="text-[10px] text-fog uppercase tracking-wider">
            运行健康
          </span>
          <span className={`badge ${connectionPresentation.tone}`}>
            {connectionPresentation.label}
          </span>
        </div>
        <div className="grid grid-cols-2 gap-2 text-xs">
          <Metric
            label="Run 状态"
            value={
              STATUS_LABELS[readModel?.status ?? "created"] ??
              readModel?.status ??
              "读取中"
            }
          />
          <Metric
            label="当前阶段"
            value={stageLabel(readModel?.active_stage_id)}
          />
          <Metric
            label="Provider 调用"
            value={String(usage?.provider_operations ?? 0)}
          />
          <Metric
            label="失败调用"
            value={String(usage?.failed_operations ?? 0)}
            tone={usage?.failed_operations ? "warning" : "default"}
          />
          <Metric
            label="合同拒绝"
            value={String(usage?.contract_rejected_operations ?? 0)}
            tone={usage?.contract_rejected_operations ? "warning" : "default"}
          />
          <Metric
            label="总 Token"
            value={formatNumber(usage?.total_tokens ?? 0)}
          />
          <Metric
            label="当前章节"
            value={
              readModel?.active_chapter_number
                ? `CH ${readModel.active_chapter_number}`
                : "—"
            }
          />
        </div>
      </div>

      <div className="p-4 border-b border-ghost shrink-0">
        <div className="text-[10px] text-fog uppercase tracking-wider mb-2">
          决策与检查点
        </div>
        <div className="flex items-center justify-between text-xs mb-2">
          <span className="text-fog">待处理决策</span>
          <span
            className={
              readModel?.pending_decisions.length
                ? "text-amber font-medium"
                : "text-mint"
            }
          >
            {readModel?.pending_decisions.length ?? 0}
          </span>
        </div>
        <div className="text-[10px] text-fog font-mono break-all">
          checkpoint · {shortRef(readModel?.checkpoint_id)}
        </div>
      </div>

      <div className="flex-1 min-h-0 overflow-y-auto p-3">
        <div className="text-[10px] text-fog uppercase tracking-wider mb-2 px-1">
          实时日志 · {events.length}
        </div>
        {recentEvents.length === 0 ? (
          <div className="text-xs text-fog px-1 py-4">等待 Run 事件…</div>
        ) : (
          recentEvents.map((event) => (
            <LogEntry key={event.event_id} event={event} />
          ))
        )}
      </div>
    </aside>
  )
}

function LogEntry({ event }: { event: RunEvent }) {
  return (
    <div className="border-l border-hairline pl-3 py-2 mb-1">
      <div className="flex items-center gap-2 mb-0.5">
        <span className="font-mono text-[10.5px] text-fog">
          {formatClock(event.occurred_at)}
        </span>
        <span className="font-mono text-[10.5px] text-action">
          #{event.sequence}
        </span>
        {event.stage_id && (
          <span className="badge badge-ash text-[10px]">
            {stageLabel(event.stage_id)}
          </span>
        )}
      </div>
      <div className="text-[11px] text-ink break-words">
        {eventLabel(event.type)}
      </div>
      {(event.chapter_id || event.node_id) && (
        <div className="text-[10.5px] text-fog truncate mt-0.5">
          {event.chapter_id || event.node_id}
        </div>
      )}
    </div>
  )
}

function TextPanel({
  title,
  value,
  wide = false,
}: {
  title: string
  value: string
  wide?: boolean
}) {
  return (
    <section
      className={`bg-surface border border-hairline rounded-lg p-4 ${
        wide ? "md:col-span-2" : ""
      }`}
    >
      <div className="text-[10px] text-fog mb-1.5">{title}</div>
      <p className="text-sm text-ink leading-relaxed">{value || "暂无"}</p>
    </section>
  )
}

function ListPanel({
  title,
  items,
  wide = false,
}: {
  title: string
  items: string[]
  wide?: boolean
}) {
  return (
    <section
      className={`bg-surface border border-hairline rounded-lg p-4 ${
        wide ? "md:col-span-2" : ""
      }`}
    >
      <div className="text-[10px] text-fog mb-2">{title}</div>
      <ul className="space-y-2">
        {items.map((item, index) => (
          <li
            key={index}
            className="text-sm text-ink leading-relaxed flex gap-2"
          >
            <span className="text-action">{index + 1}.</span>
            <span>{item}</span>
          </li>
        ))}
      </ul>
      {items.length === 0 && <p className="text-sm text-fog">暂无</p>}
    </section>
  )
}

function Metric({
  label,
  value,
  tone = "default",
}: {
  label: string
  value: string
  tone?: "default" | "warning"
}) {
  return (
    <div className="bg-elev border border-ghost rounded p-2">
      <div className="text-[10.5px] text-fog mb-1">{label}</div>
      <div
        className={`font-mono text-[11px] ${
          tone === "warning" ? "text-amber" : "text-ink"
        }`}
      >
        {value}
      </div>
    </div>
  )
}

function records(value: unknown): Record<string, unknown>[] {
  return Array.isArray(value)
    ? value.filter(
        (item): item is Record<string, unknown> =>
          Boolean(item) && typeof item === "object" && !Array.isArray(item),
      )
    : []
}

function strings(value: unknown): string[] {
  return Array.isArray(value)
    ? value.filter((item): item is string => typeof item === "string")
    : []
}

function text(value: unknown, fallback = "") {
  return typeof value === "string" ? value : fallback
}

function stageLabel(stageId?: string | null) {
  return STAGES.find((stage) => stage.id === stageId)?.label ?? "—"
}

function connectionLabel(value: string) {
  return (
    ({
      idle: "未连接",
      connecting: "连接中",
      live: "已连接",
      reconnecting: "重连中",
      closed: "已结束",
      error: "异常",
    } as Record<string, string>)[value] ?? value
  )
}

function eventLabel(value: string) {
  return (
    ({
      "run.started": "Run 已启动",
      "run.completed": "Run 已完成",
      "run.failed": "Run 失败",
      "node.started": "节点开始执行",
      "node.completed": "节点执行完成",
      "node.failed": "节点执行失败",
      "artifact.candidate_ready": "候选产物已就绪",
      "artifact.committed": "阶段产物已提交",
      "decision.required": "需要作者决策",
      "decision.resolved": "作者决策已处理",
      "review.started": "审稿开始",
      "review.completed": "审稿完成",
      "review.unavailable": "审稿暂不可用",
      "evidence.proposed": "证据提案已生成",
      "evidence.recovery_required": "证据需要恢复",
      "writeback.queued": "写回已排队",
      "writeback.committed": "写回已提交",
      "writeback.failed": "写回失败",
      "checkpoint.saved": "检查点已保存",
    } as Record<string, string>)[value] ?? value
  )
}

function formatNumber(value: number) {
  return value.toLocaleString("zh-CN")
}

function shortRef(value?: string) {
  if (!value) return "—"
  return value.length > 18 ? `${value.slice(0, 8)}…${value.slice(-6)}` : value
}

function formatClock(value: string) {
  const date = new Date(value)
  return Number.isNaN(date.getTime())
    ? value
    : date.toLocaleTimeString("zh-CN", {
        hour: "2-digit",
        minute: "2-digit",
        second: "2-digit",
      })
}
