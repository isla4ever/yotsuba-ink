import { CircleStop, RotateCcw, ShieldCheck } from "lucide-react"

type Props = {
  busy: boolean
  onCancel: () => void
  onRetry: () => void
  unitLabel: string
}

export function WritebackRecoveryNotice({
  busy,
  onCancel,
  onRetry,
  unitLabel,
}: Props) {
  return (
    <section
      aria-live="polite"
      className="page-in grid flex-none grid-cols-[30px_minmax(0,1fr)_auto] items-center gap-3 border-b border-amber/25 bg-amber-bg px-[clamp(14px,2.2vw,24px)] py-2.5 motion-reduce:!animate-none max-md:grid-cols-[30px_minmax(0,1fr)] max-md:items-start"
      data-testid="writeback-recovery-notice"
    >
      <div
        className="flex size-[30px] items-center justify-center rounded-full border border-mint/30 bg-mint-bg text-mint"
        aria-hidden="true"
      >
        <ShieldCheck size={15} />
      </div>
      <div className="grid min-w-0 gap-0.5">
        <span className="font-mono text-[8.5px] text-mint">
          {unitLabel} · 已接受不可变版本
        </span>
        <strong className="text-[10.5px] font-semibold text-ink">
          正文安全，正式事实写回待恢复
        </strong>
        <p className="m-0 text-[9.5px] leading-[1.55] text-fog">
          当前内容不会被重写。重试只会继续未完成的 Canon / Wiki
          幂等提交，不重复生成正文或推进下一个单元。
        </p>
      </div>
      <div className="flex items-center gap-1.5 max-md:col-span-2 max-md:pl-[41px] max-[440px]:grid max-[440px]:grid-cols-[minmax(0,1fr)_auto] max-[440px]:pl-0">
        <button
          className="btn btn-primary text-xs"
          disabled={busy}
          onClick={onRetry}
          type="button"
        >
          <RotateCcw size={12} />
          {busy ? "正在恢复…" : "重试正式写回"}
        </button>
        <button
          className="btn btn-ghost text-risk text-xs"
          disabled={busy}
          onClick={onCancel}
          type="button"
        >
          <CircleStop size={12} /> 取消 Run
        </button>
      </div>
    </section>
  )
}
