import type { ReactNode } from "react"
import { Plus } from "lucide-react"

export function ArchitectureTextarea({
  collaborationPath,
  collaborationUnit,
  label,
  value,
  editable,
  emphasized = false,
  rows,
  onChange,
}: {
  collaborationPath: string
  collaborationUnit: string
  label: string
  value: string
  editable: boolean
  emphasized?: boolean
  rows: number
  onChange: (value: string) => void
}) {
  if (!editable) {
    return (
      <div
        className={`book-architecture-field artifact-readable-field${
          emphasized ? " is-emphasized" : ""
        }`}
      >
        <span>{label}</span>
        <p className="artifact-readable-value">{value}</p>
      </div>
    )
  }
  return (
    <label
      className={`book-architecture-field${emphasized ? " is-emphasized" : ""}`}
    >
      <span>{label}</span>
      <textarea
        data-collaboration-field-path={collaborationPath}
        data-collaboration-unit={collaborationUnit}
        rows={rows}
        value={value}
        readOnly={!editable}
        onChange={(event) => onChange(event.target.value)}
      />
    </label>
  )
}

export function InlineComposer({
  value,
  placeholder,
  disabled,
  onChange,
  onSubmit,
}: {
  value: string
  placeholder: string
  disabled: boolean
  onChange: (value: string) => void
  onSubmit: () => void
}) {
  return (
    <div className="book-architecture-composer">
      <input
        value={value}
        placeholder={placeholder}
        onChange={(event) => onChange(event.target.value)}
        onKeyDown={(event) => {
          if (event.key !== "Enter") return
          event.preventDefault()
          onSubmit()
        }}
      />
      <button
        type="button"
        disabled={disabled || !value.trim()}
        onClick={onSubmit}
      >
        <Plus size={13} /> 添加
      </button>
    </div>
  )
}

export function ReferenceLedger({
  icon,
  label,
  refs,
}: {
  icon: ReactNode
  label: string
  refs: string[]
}) {
  return (
    <section>
      <span>
        {icon} {label}
      </span>
      <div>
        {refs.map((ref) => (
          <code key={ref}>{ref}</code>
        ))}
      </div>
    </section>
  )
}

export function shortArtifactRef(value: string) {
  return value.length > 32 ? `${value.slice(0, 18)}…${value.slice(-9)}` : value
}
