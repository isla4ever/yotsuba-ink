import { useEffect, useState, type ReactNode } from "react"
import {
  ArrowDown,
  ArrowUp,
  Clock3,
  Crosshair,
  DoorOpen,
  Flag,
  Gauge,
  MapPin,
  ShieldAlert,
  Sparkles,
  UsersRound,
} from "lucide-react"
import type {
  RollingDetailChapterDraft,
  RollingDetailReferenceContext,
  RollingDetailSceneDraft,
} from "../lib/phase32RollingDetail"
import {
  RollingDetailChapterCastScopeEditor,
  RollingDetailSceneCastScopeEditor,
} from "./RollingDetailCastScopeEditor"

type Props = {
  chapter: RollingDetailChapterDraft
  chapterIndex: number
  chapterCount: number
  editable: boolean
  allowCastScopeEditing?: boolean
  onMoveChapter: (offset: -1 | 1) => void
  onMoveScene: (sceneIndex: number, offset: -1 | 1) => void
  onPatchChapter: (patch: Partial<RollingDetailChapterDraft>) => void
  onPatchScene: (
    sceneRef: string,
    patch: Partial<RollingDetailSceneDraft>,
  ) => void
  referenceContext: RollingDetailReferenceContext
}

export function RollingDetailChapterEditor({
  allowCastScopeEditing = false,
  chapter,
  chapterIndex,
  chapterCount,
  editable,
  onMoveChapter,
  onMoveScene,
  onPatchChapter,
  onPatchScene,
  referenceContext,
}: Props) {
  const [section, setSection] = useState<"engine" | "scenes" | "handoff">(
    "engine",
  )

  useEffect(() => setSection("engine"), [chapter.chapter_ref])

  return (
    <section className="phase32-detail-blueprint">
      <header className="phase32-detail-blueprint-header">
        <div>
          <span>{String(chapter.ordinal).padStart(2, "0")}</span>
          <div>
            {editable ? (
              <label>
                <span>章节标题</span>
                <input
                  aria-label="章节标题"
                  data-collaboration-field-path={`chapters.${chapterIndex}.title`}
                  data-collaboration-unit={chapter.chapter_ref}
                  value={chapter.title}
                  onChange={(event) =>
                    onPatchChapter({ title: event.target.value })
                  }
                />
              </label>
            ) : (
              <div className="phase32-detail-title-readout">
                <span>章节标题</span>
                <strong>{chapter.title}</strong>
              </div>
            )}
            <code>{chapter.chapter_ref}</code>
          </div>
        </div>
        <div className="phase32-detail-blueprint-controls">
          {editable ? (
            <>
              <label>
                <Gauge size={12} />
                <span>软篇幅</span>
                <input
                  aria-label="章节软篇幅"
                  max={100_000}
                  min={100}
                  step={500}
                  type="number"
                  value={chapter.length_hint}
                  onChange={(event) =>
                    onPatchChapter({ length_hint: Number(event.target.value) })
                  }
                />
                <i>字</i>
              </label>
              <div aria-label="调整章节顺序">
                <IconButton
                  disabled={chapterIndex === 0}
                  label={`上移章节 ${chapter.ordinal}`}
                  onClick={() => onMoveChapter(-1)}
                >
                  <ArrowUp size={13} />
                </IconButton>
                <IconButton
                  disabled={chapterIndex === chapterCount - 1}
                  label={`下移章节 ${chapter.ordinal}`}
                  onClick={() => onMoveChapter(1)}
                >
                  <ArrowDown size={13} />
                </IconButton>
              </div>
            </>
          ) : (
            <div className="phase32-detail-length-readout">
              <Gauge size={12} />
              <span>{chapter.length_hint.toLocaleString()} 字</span>
            </div>
          )}
        </div>
      </header>

      <div className="phase32-detail-scope-strip">
        <ScopeItem icon={<Flag size={12} />} label="卷册">
          {referenceContext.volumes[chapter.volume_ref]?.label ??
            chapter.volume_ref}
        </ScopeItem>
        <ScopeItem icon={<Crosshair size={12} />} label="POV">
          {referenceContext.cast[chapter.pov_subject_ref]?.label ??
            chapter.pov_subject_ref}
        </ScopeItem>
        <ScopeItem icon={<UsersRound size={12} />} label="出场人物">
          {chapter.cast_subject_refs
            .map((ref) => referenceContext.cast[ref]?.label ?? ref)
            .join(" · ")}
        </ScopeItem>
      </div>

      {editable && allowCastScopeEditing ? (
        <RollingDetailChapterCastScopeEditor
          chapter={chapter}
          onChange={onPatchChapter}
          referenceContext={referenceContext}
        />
      ) : null}

      <nav className="artifact-section-tabs" aria-label="章节蓝图分区">
        <button
          className={section === "engine" ? "is-active" : ""}
          onClick={() => setSection("engine")}
          type="button"
        >
          章节引擎
        </button>
        <button
          className={section === "scenes" ? "is-active" : ""}
          onClick={() => setSection("scenes")}
          type="button"
        >
          场景施工 · {chapter.scenes.length}
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
        <div className="phase32-detail-engine-grid">
          <BlueprintField
            collaborationPath={`chapters.${chapterIndex}.dramatic_job`}
            collaborationUnit={chapter.chapter_ref}
            editable={editable}
            label="本章戏剧任务"
            value={chapter.dramatic_job}
            onChange={(dramatic_job) => onPatchChapter({ dramatic_job })}
          />
          <BlueprintField
            collaborationPath={`chapters.${chapterIndex}.entry_state`}
            collaborationUnit={chapter.chapter_ref}
            editable={editable}
            label="进入状态"
            value={chapter.entry_state}
            onChange={(entry_state) => onPatchChapter({ entry_state })}
          />
          <BlueprintField
            collaborationPath={`chapters.${chapterIndex}.conflict`}
            collaborationUnit={chapter.chapter_ref}
            editable={editable}
            icon={<ShieldAlert size={12} />}
            label="冲突"
            value={chapter.conflict}
            onChange={(conflict) => onPatchChapter({ conflict })}
          />
          <BlueprintField
            collaborationPath={`chapters.${chapterIndex}.stakes`}
            collaborationUnit={chapter.chapter_ref}
            editable={editable}
            icon={<Sparkles size={12} />}
            label="利害"
            value={chapter.stakes}
            onChange={(stakes) => onPatchChapter({ stakes })}
          />
        </div>
      ) : null}

      {section === "scenes" ? (
        <section className="phase32-detail-scene-ledger">
          <header>
            <div>
              <MapPin size={12} />
              <span>场景施工序列</span>
            </div>
            <strong>{chapter.scenes.length} SCENES</strong>
          </header>
          <div>
            {chapter.scenes.map((scene, sceneIndex) => (
              <article key={scene.scene_ref}>
                <header>
                  <span>S{String(scene.ordinal).padStart(2, "0")}</span>
                  <code>{scene.scene_ref}</code>
                  {editable ? (
                    <div>
                      <IconButton
                        disabled={sceneIndex === 0}
                        label={`上移场景 ${scene.ordinal}`}
                        onClick={() => onMoveScene(sceneIndex, -1)}
                      >
                        <ArrowUp size={12} />
                      </IconButton>
                      <IconButton
                        disabled={sceneIndex === chapter.scenes.length - 1}
                        label={`下移场景 ${scene.ordinal}`}
                        onClick={() => onMoveScene(sceneIndex, 1)}
                      >
                        <ArrowDown size={12} />
                      </IconButton>
                    </div>
                  ) : null}
                </header>
                <div className="phase32-detail-scene-meta">
                  <CompactInput
                    collaborationPath={`chapters.${chapterIndex}.scenes.${sceneIndex}.location`}
                    collaborationUnit={chapter.chapter_ref}
                    editable={editable}
                    icon={<MapPin size={11} />}
                    label="地点"
                    value={scene.location}
                    onChange={(location) =>
                      onPatchScene(scene.scene_ref, { location })
                    }
                  />
                  <CompactInput
                    collaborationPath={`chapters.${chapterIndex}.scenes.${sceneIndex}.time_context`}
                    collaborationUnit={chapter.chapter_ref}
                    editable={editable}
                    icon={<Clock3 size={11} />}
                    label="时间"
                    value={scene.time_context}
                    onChange={(time_context) =>
                      onPatchScene(scene.scene_ref, { time_context })
                    }
                  />
                </div>
                {allowCastScopeEditing ? (
                  <RollingDetailSceneCastScopeEditor
                    chapter={chapter}
                    onChange={(patch) => onPatchScene(scene.scene_ref, patch)}
                    referenceContext={referenceContext}
                    scene={scene}
                  />
                ) : null}
                <div className="phase32-detail-scene-flow">
                  <BlueprintField
                    collaborationPath={`chapters.${chapterIndex}.scenes.${sceneIndex}.goal`}
                    collaborationUnit={chapter.chapter_ref}
                    editable={editable}
                    label="目标"
                    rows={3}
                    value={scene.goal}
                    onChange={(goal) => onPatchScene(scene.scene_ref, { goal })}
                  />
                  <BlueprintField
                    collaborationPath={`chapters.${chapterIndex}.scenes.${sceneIndex}.opposition`}
                    collaborationUnit={chapter.chapter_ref}
                    editable={editable}
                    label="对抗"
                    rows={3}
                    value={scene.opposition}
                    onChange={(opposition) =>
                      onPatchScene(scene.scene_ref, { opposition })
                    }
                  />
                  <BlueprintField
                    collaborationPath={`chapters.${chapterIndex}.scenes.${sceneIndex}.outcome`}
                    collaborationUnit={chapter.chapter_ref}
                    editable={editable}
                    label="结果"
                    rows={3}
                    value={scene.outcome}
                    onChange={(outcome) =>
                      onPatchScene(scene.scene_ref, { outcome })
                    }
                  />
                </div>
              </article>
            ))}
          </div>
        </section>
      ) : null}

      {section === "handoff" ? (
        <div className="phase32-detail-exit-grid">
          <BlueprintField
            collaborationPath={`chapters.${chapterIndex}.exit_state`}
            collaborationUnit={chapter.chapter_ref}
            editable={editable}
            icon={<DoorOpen size={12} />}
            label="退出状态"
            value={chapter.exit_state}
            onChange={(exit_state) => onPatchChapter({ exit_state })}
          />
          <BlueprintField
            collaborationPath={`chapters.${chapterIndex}.hook`}
            collaborationUnit={chapter.chapter_ref}
            editable={editable}
            icon={<Sparkles size={12} />}
            label="章尾钩子"
            value={chapter.hook}
            onChange={(hook) => onPatchChapter({ hook })}
          />
          <BlueprintField
            collaborationPath={`chapters.${chapterIndex}.handoff`}
            collaborationUnit={chapter.chapter_ref}
            editable={editable}
            icon={<Flag size={12} />}
            label="连续性交接"
            value={chapter.handoff}
            onChange={(handoff) => onPatchChapter({ handoff })}
          />
        </div>
      ) : null}
    </section>
  )
}

function BlueprintField({
  collaborationPath,
  collaborationUnit,
  editable,
  icon,
  label,
  onChange,
  rows = 4,
  value,
}: {
  collaborationPath: string
  collaborationUnit: string
  editable: boolean
  icon?: ReactNode
  label: string
  onChange: (value: string) => void
  rows?: number
  value: string
}) {
  if (!editable) {
    return (
      <div className="phase32-detail-field artifact-readable-field">
        <span>
          {icon}
          {label}
        </span>
        <p className="artifact-readable-value">{value}</p>
      </div>
    )
  }
  return (
    <label className="phase32-detail-field">
      <span>
        {icon}
        {label}
      </span>
      <textarea
        data-collaboration-field-path={collaborationPath}
        data-collaboration-unit={collaborationUnit}
        readOnly={!editable}
        rows={rows}
        value={value}
        onChange={(event) => onChange(event.target.value)}
      />
    </label>
  )
}

function CompactInput({
  collaborationPath,
  collaborationUnit,
  editable,
  icon,
  label,
  onChange,
  value,
}: {
  collaborationPath: string
  collaborationUnit: string
  editable: boolean
  icon: ReactNode
  label: string
  onChange: (value: string) => void
  value: string
}) {
  if (!editable) {
    return (
      <div className="phase32-detail-scene-readout artifact-readable-field">
        <span>
          {icon} {label}
        </span>
        <p className="artifact-readable-value">{value}</p>
      </div>
    )
  }
  return (
    <label>
      <span>
        {icon} {label}
      </span>
      <input
        data-collaboration-field-path={collaborationPath}
        data-collaboration-unit={collaborationUnit}
        readOnly={!editable}
        value={value}
        onChange={(event) => onChange(event.target.value)}
      />
    </label>
  )
}

function IconButton({
  children,
  disabled,
  label,
  onClick,
}: {
  children: ReactNode
  disabled: boolean
  label: string
  onClick: () => void
}) {
  return (
    <button
      aria-label={label}
      disabled={disabled}
      onClick={onClick}
      title={label}
      type="button"
    >
      {children}
    </button>
  )
}

function ScopeItem({
  children,
  icon,
  label,
}: {
  children: ReactNode
  icon: ReactNode
  label: string
}) {
  return (
    <div>
      <span>
        {icon} {label}
      </span>
      <strong>{children}</strong>
    </div>
  )
}
