import { useEffect, useState, type ReactNode } from "react"
import { normalizeBeatBoardReferences } from "../lib/phase32BeatBoard"

type TextFieldProps = {
  collaborationPath: string
  collaborationUnit: string
  emphasized?: boolean
  icon?: ReactNode
  label: string
  onChange: (value: string) => void
  value: string
}

export function BeatBoardTextField({
  collaborationPath,
  collaborationUnit,
  emphasized = false,
  icon,
  label,
  onChange,
  value,
}: TextFieldProps) {
  return (
    <label
      className={`beat-board-text-field artifact-readable-field ${
        emphasized ? "is-emphasized" : ""
      }`}
    >
      <span>
        {icon}
        {label}
      </span>
      <textarea
        aria-label={label}
        data-collaboration-field-path={collaborationPath}
        data-collaboration-unit={collaborationUnit}
        onChange={(event) => onChange(event.target.value)}
        rows={emphasized ? 4 : 3}
        value={value}
      />
    </label>
  )
}

export function BeatBoardReadableField({
  emphasized = false,
  icon,
  label,
  value,
}: Omit<TextFieldProps, "collaborationPath" | "collaborationUnit" | "onChange">) {
  return (
    <div
      className={`beat-board-text-field artifact-readable-field ${
        emphasized ? "is-emphasized" : ""
      }`}
    >
      <span>
        {icon}
        {label}
      </span>
      <p className="artifact-readable-value">{value}</p>
    </div>
  )
}

export function BeatBoardReferenceEditor({
  onChange,
  value,
}: {
  onChange: (value: string[]) => void
  value: string[]
}) {
  const serialized = value.join(", ")
  const [draft, setDraft] = useState(serialized)

  useEffect(() => setDraft(serialized), [serialized])

  const commit = () => onChange(normalizeBeatBoardReferences(draft))
  return (
    <label className="beat-board-reference-editor">
      <span>Setup / Payoff 稳定引用</span>
      <input
        aria-label="Setup / Payoff 稳定引用"
        onBlur={commit}
        onChange={(event) => setDraft(event.target.value)}
        onKeyDown={(event) => {
          if (event.key !== "Enter") return
          event.preventDefault()
          commit()
        }}
        placeholder="setup-example, payoff-example"
        value={draft}
      />
      <small>用逗号或换行分隔；只编辑引用关系，不改变 Beat 身份。</small>
    </label>
  )
}

export function BeatBoardIconButton({
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
