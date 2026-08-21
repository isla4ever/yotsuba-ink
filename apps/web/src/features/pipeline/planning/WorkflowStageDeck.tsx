import { ArrowRight, Check, CircleAlert } from "lucide-react"
import {
  useEffect,
  useMemo,
  useRef,
  useState,
  type CSSProperties,
  type KeyboardEvent,
} from "react"
import type {
  QualityMode,
  WorkflowDefinition,
  WorkflowStage,
} from "../contracts/workflow"
import { stageShortLabel } from "../lib/workflowPresentation"
import { workflowDeckLayer, workflowDeckPose } from "../lib/workflowDeckLayout"

const ARTIFACT_LABELS: Record<string, string> = {
  brief: "Story Brief",
  spine: "Story Spine",
  cast: "Character Bible",
  volumes: "Volume Architecture",
  detail: "Chapter Blueprint",
  text: "Chapter Drafts",
  cover: "Cover Artifact",
  export: "Export Package",
}

function stageReady(stage: WorkflowStage) {
  if (stage.type === "export") return true
  return Boolean(
    stage.provider_profile_id &&
      stage.model_settings.model &&
      stage.prompt_template_id,
  )
}

export function WorkflowStageDeck({
  activeStageId,
  qualityMode,
  workflow,
  onSelect,
}: {
  activeStageId: string
  qualityMode: QualityMode
  workflow: WorkflowDefinition
  onSelect: (stageId: string) => void
}) {
  const viewportRef = useRef<HTMLDivElement | null>(null)
  const buttonsRef = useRef<Array<HTMLButtonElement | null>>([])
  const [viewportWidth, setViewportWidth] = useState(960)
  const items = useMemo(
    () =>
      workflow.nodes.map((stage, index) => {
        const ready = stageReady(stage)
        return {
          artifact: ARTIFACT_LABELS[stage.type] ?? stage.label,
          id: stage.id,
          label: stageShortLabel(stage),
          model:
            stage.type === "export"
              ? "系统确定性执行"
              : stage.model_settings.model || "未指定模型",
          nextStage: workflow.nodes[index + 1]
            ? stageShortLabel(workflow.nodes[index + 1])
            : "流程完成",
          ready,
          statusLabel: ready ? "配置就绪" : "配置待完善",
        }
      }),
    [workflow],
  )
  const selectedIndex = Math.max(
    0,
    items.findIndex((item) => item.id === activeStageId),
  )
  const selected = items[selectedIndex] ?? items[0]

  useEffect(() => {
    const viewport = viewportRef.current
    if (!viewport) return
    const syncWidth = () => setViewportWidth(viewport.clientWidth)
    syncWidth()
    if (typeof ResizeObserver === "undefined") return
    const observer = new ResizeObserver(syncWidth)
    observer.observe(viewport)
    return () => observer.disconnect()
  }, [])

  useEffect(() => {
    const viewport = viewportRef.current
    if (!viewport || viewport.clientWidth > 620) return
    buttonsRef.current[selectedIndex]?.scrollIntoView({
      behavior: window.matchMedia("(prefers-reduced-motion: reduce)").matches
        ? "auto"
        : "smooth",
      block: "nearest",
      inline: "center",
    })
  }, [selectedIndex])

  const handleKeyDown = (
    event: KeyboardEvent<HTMLButtonElement>,
    index: number,
  ) => {
    if (!["ArrowLeft", "ArrowRight", "Home", "End"].includes(event.key)) return
    event.preventDefault()
    const nextIndex =
      event.key === "Home"
        ? 0
        : event.key === "End"
          ? items.length - 1
          : (index + (event.key === "ArrowRight" ? 1 : items.length - 1)) %
            items.length
    const item = items[nextIndex]
    if (!item) return
    onSelect(item.id)
    buttonsRef.current[nextIndex]?.focus()
  }

  return (
    <section
      className="workflow-deck-shell"
      aria-labelledby="workflow-deck-title"
    >
      <header className="workflow-deck-head">
        <div>
          <span className="workflow-deck-eyebrow">创作流程</span>
          <h2 id="workflow-deck-title">八阶段稿件栈</h2>
        </div>
        <div className="workflow-deck-position">
          <strong>
            第 {selectedIndex + 1}/{items.length} 阶段
          </strong>
          <span>选择稿件切换配置</span>
        </div>
      </header>

      <nav
        aria-label="工作流阶段配置"
        className="workflow-deck-surface"
        data-mode={qualityMode}
        style={
          {
            "--deck-marker-position": `${15.5 + (items.length > 1 ? selectedIndex / (items.length - 1) : 0.5) * 69}%`,
          } as CSSProperties
        }
      >
        <div className="workflow-deck-viewport" ref={viewportRef}>
          <span className="workflow-deck-horizon" aria-hidden="true" />
          <ol className="workflow-deck" aria-label="八阶段稿件栈">
            {items.map((item, index) => {
              const active = item.id === activeStageId
              const pose = workflowDeckPose(index, viewportWidth, items.length)
              const StatusIcon = item.ready ? Check : CircleAlert
              return (
                <li
                  className={`workflow-sheet-slot${
                    active ? " is-selected" : ""
                  }${item.ready ? " is-ready" : " is-attention"}`}
                  key={item.id}
                  style={
                    {
                      "--deck-x": `${pose.x}px`,
                      "--deck-z": `${pose.z}px`,
                      zIndex: active
                        ? 100
                        : workflowDeckLayer(index, items.length),
                    } as CSSProperties
                  }
                >
                  <button
                    type="button"
                    className="workflow-sheet-button"
                    aria-current={active ? "step" : undefined}
                    aria-label={`第 ${index + 1} 阶段，${item.label}，${item.statusLabel}`}
                    onClick={() => onSelect(item.id)}
                    onKeyDown={(event) => handleKeyDown(event, index)}
                    ref={(node) => {
                      buttonsRef.current[index] = node
                    }}
                    tabIndex={active ? 0 : -1}
                  >
                    <span className="workflow-sheet-body" aria-hidden="true">
                      <span className="workflow-sheet-depth" />
                      <span className="workflow-sheet-stack" />
                      <span className="workflow-sheet">
                        <span className="workflow-sheet-highlight" />
                        <span className="workflow-sheet-index">
                          {String(index + 1).padStart(2, "0")}
                        </span>
                        <span className="workflow-sheet-icon">
                          <StatusIcon size={14} />
                        </span>
                        <span className="workflow-sheet-copy">
                          <strong>{item.label}</strong>
                          <small>{item.artifact}</small>
                          <span className="workflow-sheet-folio">
                            <i />
                            <i />
                            <i />
                            <i />
                          </span>
                        </span>
                        <span className="workflow-sheet-state">
                          {item.statusLabel}
                        </span>
                      </span>
                    </span>
                  </button>
                </li>
              )
            })}
          </ol>
          <div className="workflow-deck-pedestal" aria-hidden="true">
            <span />
            <i />
          </div>
        </div>

        {selected && (
          <footer className="workflow-deck-caption">
            <div>
              <p>
                <span
                  className={`workflow-status-dot ${
                    selected.ready ? "is-ready" : "is-attention"
                  }`}
                />
                当前阶段
              </p>
              <h3>{selected.label}</h3>
              <span>{selected.artifact}</span>
            </div>
            <div>
              <small>配置状态</small>
              <strong>{selected.statusLabel}</strong>
            </div>
            <div>
              <small>执行模型</small>
              <strong title={selected.model}>{selected.model}</strong>
            </div>
            <div>
              <small>下一阶段</small>
              <strong>
                {selected.nextStage}
                <ArrowRight size={13} />
              </strong>
            </div>
          </footer>
        )}
      </nav>
    </section>
  )
}
