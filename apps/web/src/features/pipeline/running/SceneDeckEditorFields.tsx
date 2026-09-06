import type { ReactNode } from "react"
import type {
  SceneDeckCastMember,
  SceneDeckSceneDraft,
} from "../lib/phase32SceneDeck"

type SceneTextFieldProps = {
  collaborationPath: string
  collaborationUnit: string
  emphasized?: boolean
  icon?: ReactNode
  label: string
  onChange: (value: string) => void
  value: string
}

export function SceneDeckTextField({
  collaborationPath,
  collaborationUnit,
  emphasized = false,
  icon,
  label,
  onChange,
  value,
}: SceneTextFieldProps) {
  return (
    <label
      className={`scene-deck-text-field artifact-readable-field ${
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

export function SceneDeckReadableField({
  emphasized = false,
  icon,
  label,
  value,
}: Omit<SceneTextFieldProps, "collaborationPath" | "collaborationUnit" | "onChange">) {
  return (
    <div
      className={`scene-deck-text-field artifact-readable-field ${
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

export function SceneDeckMetadataField({
  collaborationPath,
  collaborationUnit,
  label,
  onChange,
  value,
}: {
  collaborationPath: string
  collaborationUnit: string
  label: string
  onChange: (value: string) => void
  value: string
}) {
  return (
    <label className="scene-deck-metadata-field">
      <span>{label}</span>
      <input
        aria-label={label}
        data-collaboration-field-path={collaborationPath}
        data-collaboration-unit={collaborationUnit}
        onChange={(event) => onChange(event.target.value)}
        value={value}
      />
    </label>
  )
}

export function SceneDeckCastEditor({
  cast,
  onChange,
  scene,
}: {
  cast: Record<string, SceneDeckCastMember>
  onChange: (refs: string[]) => void
  scene: SceneDeckSceneDraft
}) {
  const entries = Object.values(cast)
  return (
    <fieldset className="scene-deck-cast-editor">
      <legend>本场出场人物</legend>
      <div>
        {entries.map((member) => {
          const checked = scene.cast_subject_refs.includes(member.ref)
          return (
            <label className={checked ? "is-selected" : ""} key={member.ref}>
              <input
                aria-label={`出场人物 ${member.label}`}
                checked={checked}
                onChange={() => {
                  const next = checked
                    ? scene.cast_subject_refs.filter(
                        (ref) => ref !== member.ref,
                      )
                    : [...scene.cast_subject_refs, member.ref]
                  if (next.length) onChange(next)
                }}
                type="checkbox"
              />
              <span>{member.label}</span>
              <small>{member.role || member.ref}</small>
            </label>
          )
        })}
      </div>
      <small>至少保留一名已确认人物；不能在 Scene Deck 新建角色身份。</small>
    </fieldset>
  )
}

export function SceneDeckIconButton({
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
