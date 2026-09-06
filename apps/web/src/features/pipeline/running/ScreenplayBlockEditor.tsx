import type { ReactNode } from "react"
import { ArrowDown, ArrowUp, Plus, Trash2 } from "lucide-react"
import type {
  ScreenplayBlockDraft,
  ScreenplayBlockKind,
  ScreenplayCastMember,
} from "../lib/phase32Screenplay"

const KIND_LABELS: Record<ScreenplayBlockKind, string> = {
  scene_heading: "场景标题",
  action: "动作",
  dialogue: "对白",
  parenthetical: "括注",
  transition: "转场",
}

export function ScreenplayBlockEditor({
  blocks,
  cast,
  sceneRef,
  sceneCastRefs,
  onChange,
}: {
  blocks: ScreenplayBlockDraft[]
  cast: Record<string, ScreenplayCastMember>
  sceneRef: string
  sceneCastRefs: string[]
  onChange: (blocks: ScreenplayBlockDraft[]) => void
}) {
  const patch = (index: number, value: ScreenplayBlockDraft) =>
    onChange(
      blocks.map((block, itemIndex) => (itemIndex === index ? value : block)),
    )
  const move = (index: number, offset: -1 | 1) => {
    const target = index + offset
    if (index < 1 || target < 1 || target >= blocks.length) return
    const next = [...blocks]
    ;[next[index], next[target]] = [next[target], next[index]]
    onChange(next)
  }

  return (
    <div className="screenplay-block-editor">
      {blocks.map((block, index) => {
        const locked = index === 0
        return (
          <article
            className={`screenplay-edit-block kind-${block.kind}`}
            key={`${index}-${block.kind}`}
          >
            <header>
              <span>{String(index + 1).padStart(2, "0")}</span>
              {locked ? (
                <strong>冻结场景标题</strong>
              ) : (
                <select
                  aria-label={`正文块 ${index + 1} 类型`}
                  onChange={(event) => {
                    const kind = event.target.value as ScreenplayBlockKind
                    const bindsSpeaker = ["dialogue", "parenthetical"].includes(
                      kind,
                    )
                    patch(index, {
                      kind,
                      text: block.text,
                      ...(bindsSpeaker
                        ? {
                            speaker_ref:
                              block.speaker_ref || sceneCastRefs[0] || "",
                          }
                        : {}),
                    })
                  }}
                  value={block.kind}
                >
                  {Object.entries(KIND_LABELS)
                    .filter(([kind]) => kind !== "scene_heading")
                    .map(([kind, label]) => (
                      <option key={kind} value={kind}>
                        {label}
                      </option>
                    ))}
                </select>
              )}
              {!locked ? (
                <div>
                  <IconButton
                    disabled={index === 1}
                    label={`上移正文块 ${index + 1}`}
                    onClick={() => move(index, -1)}
                  >
                    <ArrowUp size={12} />
                  </IconButton>
                  <IconButton
                    disabled={index === blocks.length - 1}
                    label={`下移正文块 ${index + 1}`}
                    onClick={() => move(index, 1)}
                  >
                    <ArrowDown size={12} />
                  </IconButton>
                  <IconButton
                    disabled={blocks.length <= 2}
                    label={`删除正文块 ${index + 1}`}
                    onClick={() =>
                      onChange(
                        blocks.filter((_, itemIndex) => itemIndex !== index),
                      )
                    }
                  >
                    <Trash2 size={12} />
                  </IconButton>
                </div>
              ) : null}
            </header>
            {["dialogue", "parenthetical"].includes(block.kind) ? (
              <label className="screenplay-speaker-field">
                <span>人物</span>
                <select
                  aria-label={`正文块 ${index + 1} 人物`}
                  onChange={(event) =>
                    patch(index, {
                      ...block,
                      speaker_ref: event.target.value || undefined,
                    })
                  }
                  value={block.speaker_ref ?? ""}
                >
                  {block.kind === "parenthetical" ? (
                    <option value="">不绑定人物</option>
                  ) : null}
                  {sceneCastRefs.map((ref) => (
                    <option key={ref} value={ref}>
                      {cast[ref]?.displayName ?? ref}
                    </option>
                  ))}
                </select>
              </label>
            ) : null}
            {locked ? (
              <p>{block.text}</p>
            ) : (
              <textarea
                aria-label={`正文块 ${index + 1} 内容`}
                data-collaboration-field-path={`blocks.${index}.text`}
                data-collaboration-unit={sceneRef}
                onChange={(event) =>
                  patch(index, { ...block, text: event.target.value })
                }
                rows={block.kind === "action" ? 3 : 2}
                value={block.text}
              />
            )}
          </article>
        )
      })}
      <button
        className="screenplay-add-block"
        onClick={() =>
          onChange([...blocks, { kind: "action", text: "新的可见行动。" }])
        }
        type="button"
      >
        <Plus size={13} /> 添加正文块
      </button>
    </div>
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
