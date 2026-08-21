import { useEffect, useMemo, useState } from "react"
import {
  BookOpen,
  CheckCircle2,
  ChevronRight,
  Flag,
  GitBranch,
  Layers3,
  Lock,
  Users,
} from "lucide-react"
import { useApp } from "../state/PipelineAppProvider"
import {
  parseCharacterBibleArtifact,
  parseStoryBriefArtifact,
  parseVolumeArchitectureArtifact,
  type VolumeContract,
} from "@/features/pipeline/contracts/artifacts"
import { BookLoader } from "@/features/pipeline/layout/BookLoader"
import { useLoadingPresence } from "@/features/pipeline/layout/useLoadingPresence"
import { stageDecisionFor } from "@/features/pipeline/lib/stageDecision"
import { useStageArtifactDraft } from "@/features/pipeline/state/useStageArtifactDraft"
import { StageCandidateActions } from "@/features/pipeline/running/StageCandidateActions"
import {
  detailChapterCounts,
  volumeCastNames,
  volumeLengthLabel,
  volumeTurnRange,
} from "@/features/pipeline/lib/volumePresentation"

export default function VolumesStageView() {
  const {
    activeProject,
    activeRun,
    refreshRun,
    runArtifactError,
    runArtifactLoading,
    runArtifacts,
    runCandidateArtifacts,
    runLoading,
    selectedVolumeId,
    setRoute,
    setSelectedVolumeId,
  } = useApp()
  const decision = useMemo(
    () => stageDecisionFor(activeRun, "volumes"),
    [activeRun],
  )
  const committed = runArtifacts.volumes
  const candidate = runCandidateArtifacts.volumes
  const source = decision ? candidate : committed
  const runId = activeRun?.definition.run_id ?? ""
  const draft = useStageArtifactDraft(runId, decision, source)
  const parsed = useMemo(
    () => parseVolumeArchitectureArtifact(draft.artifact ?? source?.payload),
    [draft.artifact, source],
  )
  const cast = useMemo(
    () => parseCharacterBibleArtifact(runArtifacts.cast?.payload),
    [runArtifacts.cast],
  )
  const brief = useMemo(
    () => parseStoryBriefArtifact(runArtifacts.brief?.payload),
    [runArtifacts.brief],
  )
  const chapterCounts = useMemo(
    () => detailChapterCounts(runArtifacts.detail?.payload),
    [runArtifacts.detail],
  )
  const artifact = parsed.artifact
  const volumeSignature =
    artifact?.volumes.map((volume) => volume.id).join("|") ?? ""

  useEffect(() => {
    if (!artifact?.volumes.length) return
    if (!artifact.volumes.some((volume) => volume.id === selectedVolumeId))
      setSelectedVolumeId(artifact.volumes[0].id)
  }, [artifact, selectedVolumeId, setSelectedVolumeId, volumeSignature])

  const initialLoad = useLoadingPresence(runLoading || runArtifactLoading)

  if (initialLoad.visible) {
    return (
      <BookLoader
        phase={initialLoad.exiting ? "exit" : "enter"}
        variant="panel"
        label="正在装订分卷架构"
        detail="同步自然卷界、卷合同与章节容量"
      />
    )
  }

  if (!activeProject?.latestRunId || !activeRun) {
    return (
      <VolumesEmpty
        title="当前作品尚未启动创作 Run"
        detail="人物编排确认后，系统才会生成自然卷界与分卷合同。"
        onBack={() => setRoute("studio")}
      />
    )
  }

  if (!source || !artifact) {
    return (
      <VolumesEmpty
        title="分卷架构尚未就绪"
        detail={
          runArtifactError ||
          parsed.error ||
          "请先完成角色阶段并等待 Volumes Artifact。"
        }
        onBack={() => setRoute("cast")}
      />
    )
  }

  const selected =
    artifact.volumes.find((volume) => volume.id === selectedVolumeId) ??
    artifact.volumes[0]
  const selectedIndex = artifact.volumes.findIndex(
    (volume) => volume.id === selected.id,
  )
  const editable = Boolean(decision && candidate)
  const updateSelected = (patch: Partial<VolumeContract>) => {
    if (!editable) return
    draft.change({
      ...artifact,
      volumes: artifact.volumes.map((volume, index) =>
        index === selectedIndex ? { ...volume, ...patch } : volume,
      ),
    } as unknown as Record<string, unknown>)
  }
  const totalTurns = artifact.volumes.reduce(
    (sum, volume) => sum + volume.turn_refs.length,
    0,
  )
  const totalChapters = [...chapterCounts.values()].reduce(
    (sum, count) => sum + count,
    0,
  )
  const target =
    brief.artifact?.length_envelope.word_target_soft ??
    activeProject.targetWordCount

  return (
    <div className="volumes-screen page-in">
      <header className="volumes-stage-bar stage-aura">
        <div className="volumes-stage-status">
          <CheckCircle2 size={14} />
          <div>
            <strong>{decision ? "分卷候选待确认" : "分卷架构已定稿"}</strong>
            <span>
              {artifact.volumes.length} 卷 · {totalTurns} 个因果转折 · 目标{" "}
              {formatTarget(target)}
            </span>
          </div>
        </div>
        {decision ? (
          <StageCandidateActions
            acceptLabel="确认分卷架构"
            artifact={artifact as unknown as Record<string, unknown>}
            decision={decision}
            disabled={!editable}
            draftStatus={draft.status}
            onResolved={refreshRun}
            regenerateDescription="只调整卷名、读者承诺、核心冲突、高潮和收束表达；卷数、顺序、Turn 归属与人物范围继续使用冻结合同。"
            regeneratePlaceholder="例如：第二卷更早兑现职业危机，让高潮同时推动真相与关系破裂。"
            regenerateTitle="定向重做分卷架构"
            runId={runId}
          />
        ) : (
          <button
            type="button"
            className="btn btn-primary text-xs"
            onClick={() => setRoute("detail")}
          >
            前往细纲 <ChevronRight size={14} />
          </button>
        )}
      </header>

      {(draft.error || runArtifactError) && (
        <div className="mx-4 md:mx-5 mt-3 banner-warning" role="alert">
          {draft.error || runArtifactError}
        </div>
      )}

      <div className="volumes-workbench">
        <aside className="volumes-rail" aria-label="分卷导航">
          <header>
            <span>分卷轨道</span>
            <strong>{artifact.volumes.length} VOLUMES</strong>
          </header>
          <nav>
            {artifact.volumes.map((volume, index) => (
              <button
                key={volume.id}
                type="button"
                className={volume.id === selected.id ? "active" : ""}
                onClick={() => setSelectedVolumeId(volume.id)}
              >
                <span>{String(index + 1).padStart(2, "0")}</span>
                <div>
                  <strong>{volume.title}</strong>
                  <small>
                    {volumeTurnRange(volume)} ·{" "}
                    {volumeLengthLabel(volume.length_hint)}
                  </small>
                </div>
                <em>
                  {chapterCounts.get(volume.id)
                    ? `${chapterCounts.get(volume.id)} 章`
                    : "待细纲"}
                </em>
              </button>
            ))}
          </nav>
          <footer>
            <span>下游章节投影</span>
            <strong>
              {totalChapters ? `${totalChapters} 章已分配` : "尚未进入细纲"}
            </strong>
          </footer>
        </aside>

        <main className="volume-contract-workspace" key={selected.id}>
          <header className="volume-contract-heading">
            <div>
              <span>
                {selected.id.toUpperCase()} · {volumeTurnRange(selected)}
              </span>
              <input
                aria-label="卷名"
                className="volume-title-input"
                data-collaboration-field-path={`volumes.${selectedIndex}.title`}
                data-collaboration-unit={selected.id}
                maxLength={12}
                minLength={2}
                onChange={(event) => updateSelected({ title: event.target.value })}
                readOnly={!editable}
                value={selected.title}
              />
            </div>
            <div className="volume-contract-badges">
              <span className="badge badge-action">
                {volumeLengthLabel(selected.length_hint)}
              </span>
              <span className="badge badge-ash">
                <BookOpen size={10} />
                {chapterCounts.get(selected.id)
                  ? `${chapterCounts.get(selected.id)} 章`
                  : "章节待分配"}
              </span>
            </div>
          </header>

          <section className="volume-contract-sheet" aria-label="卷合同">
            <div className="volume-rhythm-rail" aria-hidden="true">
              <strong>卷内节奏</strong>
              <ol>
                <li>承诺</li>
                <li>施压</li>
                <li className="active">高潮</li>
                <li>收束</li>
              </ol>
            </div>
            <div className="volume-contract-flow">
              <ContractBeat
                index="01"
                label="读者承诺"
                icon={Layers3}
                tone="promise"
                note="本卷必须兑现"
                content={selected.promise}
                editable={editable}
                fieldPath={`volumes.${selectedIndex}.promise`}
                onChange={(promise) => updateSelected({ promise })}
                unitRef={selected.id}
              />
              <ContractBeat
                index="02"
                label="核心冲突"
                icon={GitBranch}
                tone="conflict"
                note="贯穿本卷施压"
                content={selected.conflict}
                editable={editable}
                fieldPath={`volumes.${selectedIndex}.conflict`}
                onChange={(conflict) => updateSelected({ conflict })}
                unitRef={selected.id}
              />
              <ContractBeat
                index="03"
                label="本卷高潮"
                icon={Flag}
                tone="climax"
                note="不可逆的转折"
                content={selected.climax}
                editable={editable}
                fieldPath={`volumes.${selectedIndex}.climax`}
                onChange={(climax) => updateSelected({ climax })}
                unitRef={selected.id}
                meta={selected.climax_turn_ref.replace("turn-", "T")}
                highlight
              />
              <ContractBeat
                index="04"
                label="闭合格局"
                icon={Lock}
                tone="closure"
                note="交接下一卷"
                content={selected.closure}
                editable={editable}
                fieldPath={`volumes.${selectedIndex}.closure`}
                onChange={(closure) => updateSelected({ closure })}
                unitRef={selected.id}
              />
            </div>
          </section>

          <section className="volume-contract-ledgers">
            <div className="volume-turn-ledger">
              <header>
                <span>
                  <GitBranch size={12} />
                  因果归属
                </span>
                <strong>{selected.turn_refs.length} TURNS</strong>
              </header>
              <div>
                {selected.turn_refs.map((turn) => (
                  <span
                    key={turn}
                    className={
                      turn === selected.climax_turn_ref ? "climax" : ""
                    }
                  >
                    {turn.replace("turn-", "T")}
                  </span>
                ))}
              </div>
            </div>
            <div className="volume-cast-ledger">
              <header>
                <span>
                  <Users size={12} />
                  本卷主体
                </span>
                <strong>{selected.cast_ids.length} SUBJECTS</strong>
              </header>
              <div>
                {volumeCastNames(selected, cast.artifact).map((subject) => (
                  <span key={subject.id} title={subject.id}>
                    {subject.name}
                  </span>
                ))}
              </div>
            </div>
          </section>

          <footer className="volume-artifact-foot">
            <span>正式来源</span>
            <strong>{source.artifact_id}</strong>
            <em>卷卡、节奏与章节数量均为 Artifact/Detail 的可重建投影</em>
          </footer>
        </main>
      </div>
    </div>
  )
}

function ContractBeat({
  content,
  editable,
  fieldPath,
  highlight,
  icon: Icon,
  index,
  label,
  meta,
  note,
  onChange,
  tone,
  unitRef,
}: {
  content: string
  editable: boolean
  fieldPath: string
  highlight?: boolean
  icon: typeof Layers3
  index: string
  label: string
  meta?: string
  note: string
  onChange: (value: string) => void
  tone: "promise" | "conflict" | "climax" | "closure"
  unitRef: string
}) {
  return (
    <article
      className={`volume-contract-beat volume-contract-beat-${tone} ${
        highlight ? "highlight" : ""
      }`}
    >
      <header>
        <span>{index}</span>
        <Icon size={12} />
        <div>
          <strong>{label}</strong>
          <small>{note}</small>
        </div>
        {meta && <em>{meta}</em>}
      </header>
      <textarea
        aria-label={label}
        data-collaboration-field-path={fieldPath}
        data-collaboration-unit={unitRef}
        onChange={(event) => onChange(event.target.value)}
        readOnly={!editable}
        rows={4}
        value={content}
      />
    </article>
  )
}

function VolumesEmpty({
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
        <Layers3 size={23} className="text-fog mx-auto mb-3" />
        <h1 className="text-sm font-semibold text-ink mb-1">{title}</h1>
        <p className="text-xs text-fog mb-4">{detail}</p>
        <button
          type="button"
          className="btn btn-secondary text-xs"
          onClick={onBack}
        >
          返回上一步
        </button>
      </div>
    </div>
  )
}

function formatTarget(value: number) {
  return value >= 10_000
    ? `${(value / 10_000).toFixed(value % 10_000 ? 1 : 0)} 万字`
    : `${value.toLocaleString("zh-CN")} 字`
}
