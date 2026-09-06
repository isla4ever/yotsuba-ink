import type { ReactNode } from "react"

export function SectionPlanTextField({
  collaborationPath,
  collaborationUnit,
  editable,
  emphasized = false,
  icon,
  label,
  onChange,
  rows = 5,
  value,
}: {
  collaborationPath: string
  collaborationUnit: string
  editable: boolean
  emphasized?: boolean
  icon?: ReactNode
  label: string
  onChange: (value: string) => void
  rows?: number
  value: string
}) {
  if (!editable) {
    return (
      <div
        className={`section-plan-text-field artifact-readable-field${
          emphasized ? " is-emphasized" : ""
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
  return (
    <label
      className={`section-plan-text-field${emphasized ? " is-emphasized" : ""}`}
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
        rows={rows}
        value={value}
      />
    </label>
  )
}

export function SectionPlanContextCell({
  children,
  eyebrow,
  icon,
  tone = "quiet",
}: {
  children: ReactNode
  eyebrow: string
  icon: ReactNode
  tone?: "active" | "quiet"
}) {
  return (
    <article className={tone === "active" ? "is-active" : ""}>
      <span>
        {icon}
        {eyebrow}
      </span>
      <p>{children}</p>
    </article>
  )
}

export function shortSectionPlanRef(value: string) {
  return value.length > 31 ? `${value.slice(0, 18)}…${value.slice(-9)}` : value
}
