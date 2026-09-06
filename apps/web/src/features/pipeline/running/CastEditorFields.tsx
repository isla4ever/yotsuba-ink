import { Plus, Trash2 } from "lucide-react"

export function CastTextarea({
  collaborationPath,
  collaborationUnit,
  editable,
  emphasized = false,
  label,
  onChange,
  rows,
  value,
}: {
  collaborationPath: string
  collaborationUnit: string
  editable: boolean
  emphasized?: boolean
  label: string
  onChange: (value: string) => void
  rows: number
  value: string
}) {
  if (!editable) {
    return (
      <div
        className={`phase32-cast-field artifact-readable-field${
          emphasized ? " is-emphasized" : ""
        }`}
        data-collaboration-field-path={collaborationPath}
        data-collaboration-unit={collaborationUnit}
      >
        <span>{label}</span>
        <p className="artifact-readable-value">{value}</p>
      </div>
    )
  }
  return (
    <label
      className={`phase32-cast-field${emphasized ? " is-emphasized" : ""}`}
    >
      <span>{label}</span>
      <textarea
        data-collaboration-field-path={collaborationPath}
        data-collaboration-unit={collaborationUnit}
        onChange={(event) => onChange(event.target.value)}
        readOnly={!editable}
        rows={rows}
        value={value}
      />
    </label>
  )
}

export function CastConstraintEditor({
  constraints,
  editable,
  onChange,
  subjectIndex,
  subjectRef,
}: {
  constraints: string[]
  editable: boolean
  onChange: (constraints: string[]) => void
  subjectIndex: number
  subjectRef: string
}) {
  const update = (index: number, value: string) =>
    onChange(
      constraints.map((constraint, constraintIndex) =>
        constraintIndex === index ? value : constraint,
      ),
    )
  const remove = (index: number) => {
    if (constraints.length <= 1) return
    onChange(
      constraints.filter((_, constraintIndex) => constraintIndex !== index),
    )
  }
  const add = () => {
    if (constraints.length >= 16) return
    onChange([...constraints, "新的限制条件"])
  }

  return (
    <section className="phase32-cast-constraint-editor">
      <header>
        <span>行动限制</span>
        <small>{constraints.length}/16</small>
      </header>
      <div>
        {constraints.map((constraint, index) =>
          editable ? (
            <label key={index}>
              <span>{String(index + 1).padStart(2, "0")}</span>
              <input
                aria-label={`行动限制 ${index + 1}`}
                data-collaboration-field-path={`characters.${subjectIndex}.constraints.${index}`}
                data-collaboration-unit={subjectRef}
                onChange={(event) => update(index, event.target.value)}
                value={constraint}
              />
              <button
                aria-label={`删除行动限制 ${index + 1}`}
                disabled={constraints.length <= 1}
                onClick={() => remove(index)}
                title="删除限制"
                type="button"
              >
                <Trash2 size={12} />
              </button>
            </label>
          ) : (
            <div className="phase32-cast-constraint-row" key={index}>
              <span>{String(index + 1).padStart(2, "0")}</span>
              <p>{constraint}</p>
            </div>
          ),
        )}
      </div>
      {editable ? (
        <button
          className="phase32-cast-add-constraint"
          disabled={constraints.length >= 16}
          onClick={add}
          type="button"
        >
          <Plus size={12} /> 添加限制
        </button>
      ) : null}
    </section>
  )
}
