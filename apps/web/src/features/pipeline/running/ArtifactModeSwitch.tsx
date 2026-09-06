import { Eye, PenLine } from "lucide-react"

export function ArtifactModeSwitch({
  canEdit,
  editLabel = "编辑",
  editTitle = "编辑模式",
  editing,
  onEdit,
  onShow,
}: {
  canEdit: boolean
  editLabel?: string
  editTitle?: string
  editing: boolean
  onEdit: () => void
  onShow: () => void
}) {
  return (
    <div className="artifact-mode-switch" aria-label="内容呈现模式">
      <button
        aria-label="阅读模式"
        aria-pressed={!editing}
        className={!editing ? "is-active" : ""}
        onClick={onShow}
        title="阅读模式"
        type="button"
      >
        <Eye size={12} />
        <span>阅读</span>
      </button>
      <button
        aria-label={editTitle}
        aria-pressed={editing}
        className={editing ? "is-active" : ""}
        disabled={!canEdit}
        onClick={onEdit}
        title={editTitle}
        type="button"
      >
        <PenLine size={12} />
        <span>{editLabel}</span>
      </button>
    </div>
  )
}
