import type { ReactNode } from "react"

export function VolumeContractField({
  collaborationPath,
  collaborationUnit,
  icon,
  label,
  value,
  editable,
  onChange,
}: {
  collaborationPath: string
  collaborationUnit: string
  icon: ReactNode
  label: string
  value: string
  editable: boolean
  onChange: (value: string) => void
}) {
  if (!editable) {
    return (
      <div className="phase32-volume-field artifact-readable-field">
        <span>
          {icon} {label}
        </span>
        <p className="artifact-readable-value">{value}</p>
      </div>
    )
  }
  return (
    <label className="phase32-volume-field">
      <span>
        {icon}
        {label}
      </span>
      <textarea
        data-collaboration-field-path={collaborationPath}
        data-collaboration-unit={collaborationUnit}
        rows={4}
        value={value}
        readOnly={!editable}
        onChange={(event) => onChange(event.target.value)}
      />
    </label>
  )
}

export function VolumeScopeLedger({
  icon,
  label,
  children,
}: {
  icon: ReactNode
  label: string
  children: ReactNode
}) {
  return (
    <section className="phase32-volume-scope-ledger">
      <span>
        {icon}
        {label}
      </span>
      <div>{children}</div>
    </section>
  )
}

export function shortPhase32ArtifactRef(value: string) {
  if (value.length <= 31) return value
  return `${value.slice(0, 18)}…${value.slice(-9)}`
}
