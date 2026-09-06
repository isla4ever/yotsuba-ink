import type { ReactNode } from "react"
import {
  CheckCircle2,
  FileArchive,
  Image,
  ImageOff,
  Package,
} from "lucide-react"

type DeliveryStage = "cover" | "export"

const LABELS = {
  cover: {
    completed: "封面已定稿",
    running: "封面生成中",
    locked: "封面尚未解锁",
    awaiting: "封面等待决策",
  },
  export: {
    completed: "交付包已物化",
    running: "正在编制导出",
    locked: "导出尚未解锁",
    awaiting: "导出等待决策",
  },
} as const

export function DeliveryStageBar({
  stage,
  status,
  detail,
  children,
}: {
  stage: DeliveryStage
  status: string
  detail: string
  children?: ReactNode
}) {
  const completed = status === "completed"
  const Icon = stage === "cover" ? Image : Package
  const labels = LABELS[stage]
  const label = completed
    ? labels.completed
    : status === "running"
      ? labels.running
      : status === "locked"
        ? labels.locked
        : labels.awaiting
  return (
    <div className="stage-aura border-b border-hairline bg-surface px-4 md:px-6 py-3 flex items-center gap-3 shrink-0">
      <div className="flex items-center gap-2 flex-1 min-w-0">
        {completed ? (
          <CheckCircle2 size={13} className="text-mint shrink-0" />
        ) : (
          <Icon size={13} className="text-action shrink-0" />
        )}
        <span
          className={`text-xs font-medium ${
            completed ? "text-mint" : "text-action"
          }`}
        >
          {label}
        </span>
        <span className="hidden md:inline text-[10px] font-mono text-fog truncate">
          · {detail}
        </span>
      </div>
      {children}
    </div>
  )
}

export function DeliveryEmpty({
  stage,
  detail,
  onBack,
  title,
}: {
  stage: DeliveryStage
  detail: string
  onBack: () => void
  title: string
}) {
  const Icon = stage === "cover" ? ImageOff : FileArchive
  return (
    <div className="max-w-md text-center page-in">
      <Icon size={24} className="text-fog mx-auto mb-3" />
      <h1 className="text-sm font-semibold text-ink mb-1">{title}</h1>
      <p className="text-xs text-fog leading-6 mb-4">{detail}</p>
      <button
        type="button"
        className="btn btn-secondary text-xs"
        onClick={onBack}
      >
        {stage === "cover" ? "返回上一步" : "返回封面阶段"}
      </button>
    </div>
  )
}

export function DeliveryDecisionDialog({
  title,
  children,
  onClose,
}: {
  title: string
  children: ReactNode
  onClose: () => void
}) {
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center px-4">
      <button
        type="button"
        className="absolute inset-0 bg-black/55 backdrop-blur-sm"
        onClick={onClose}
        aria-label="关闭对话框"
      />
      <section className="relative bg-elev border border-hairline rounded-lg w-full max-w-md p-5 animate-fade-in">
        <h2 className="text-sm font-semibold text-ink mb-3">{title}</h2>
        {children}
      </section>
    </div>
  )
}

export function deliveryDraftStatusLabel(status: string) {
  if (status === "saving") return "保存中"
  if (status === "saved") return "草稿已保存"
  if (status === "dirty") return "有未保存修改"
  if (status === "error") return "草稿保存失败"
  return "候选稿已同步"
}
