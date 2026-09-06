export type Phase32DecisionDialogKind = "regenerate" | "cancel"

type Props = {
  busy: boolean
  direction: string
  error: string
  id: string
  kind: Phase32DecisionDialogKind
  placeholder: string
  regenerateDescription: string
  suggestions?: readonly string[]
  onClose: () => void
  onDirectionChange: (value: string) => void
  onSubmit: () => void
}

export function Phase32StageDecisionDialog({
  busy,
  direction,
  error,
  id,
  kind,
  placeholder,
  regenerateDescription,
  suggestions = [],
  onClose,
  onDirectionChange,
  onSubmit,
}: Props) {
  return (
    <div
      className="stage-candidate-dialog-backdrop"
      role="presentation"
      onMouseDown={onClose}
    >
      <section
        className="stage-candidate-dialog"
        role="dialog"
        aria-modal="true"
        aria-labelledby={`${id}-title`}
        onKeyDown={(event) => {
          if (event.key !== "Escape" || busy) return
          event.preventDefault()
          onClose()
        }}
        onMouseDown={(event) => event.stopPropagation()}
      >
        <span className="stage-candidate-dialog-kicker">
          {kind === "cancel" ? "停止执行" : "同一冻结合同"}
        </span>
        <h2 id={`${id}-title`}>
          {kind === "cancel" ? "取消当前创作 Run？" : "定向换一稿"}
        </h2>
        <p>
          {kind === "cancel"
            ? "已经正式提交的 Artifact 会保留；当前 Run 停止，不再推进下游。"
            : regenerateDescription}
        </p>
        {kind === "regenerate" ? (
          <>
            {suggestions.length > 0 ? (
              <div
                className="stage-candidate-suggestions"
                aria-label="换稿方向建议"
              >
                {suggestions.map((suggestion) => (
                  <button
                    type="button"
                    className={direction === suggestion ? "is-active" : ""}
                    key={suggestion}
                    onClick={() => onDirectionChange(suggestion)}
                  >
                    {suggestion}
                  </button>
                ))}
              </div>
            ) : null}
            <label>
              <span>修订方向</span>
              <textarea
                className="input"
                rows={4}
                autoFocus
                value={direction}
                onChange={(event) => onDirectionChange(event.target.value)}
                placeholder={placeholder}
              />
            </label>
          </>
        ) : null}
        {error ? (
          <p className="stage-candidate-dialog-error" role="alert">
            {error}
          </p>
        ) : null}
        <footer>
          <button
            type="button"
            className="btn btn-secondary text-xs"
            autoFocus={kind === "cancel"}
            disabled={busy}
            onClick={onClose}
          >
            返回
          </button>
          <button
            type="button"
            className={`btn text-xs ${
              kind === "cancel" ? "btn-danger" : "btn-primary"
            }`}
            disabled={busy || (kind === "regenerate" && !direction.trim())}
            onClick={onSubmit}
          >
            {busy ? "正在提交…" : kind === "cancel" ? "确认取消" : "开始换稿"}
          </button>
        </footer>
      </section>
    </div>
  )
}
