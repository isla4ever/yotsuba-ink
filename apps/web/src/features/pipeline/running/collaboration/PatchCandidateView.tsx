import { AlertTriangle, LockKeyhole, RotateCcw, X } from "lucide-react"
import type { ArtifactPatchCandidate } from "../../contracts/authorCollaboration"

type Props = {
  before: string
  disabled: boolean
  onReject: () => void
  patch: ArtifactPatchCandidate
}

export function PatchCandidateView({
  before,
  disabled,
  onReject,
  patch,
}: Props) {
  const operation = patch.operations[0]
  if (!operation) return null
  return (
    <section className="collaboration-patch" data-status={patch.status}>
      <header>
        <div>
          <RotateCcw size={14} />
          <strong>改稿候选</strong>
        </div>
        <span>{patchStatusLabel(patch.status)}</span>
      </header>
      <div className="collaboration-patch-diff">
        <div>
          <span>原文</span>
          <p>{before}</p>
        </div>
        <div>
          <span>建议稿</span>
          <p>{operation.replacement}</p>
        </div>
      </div>
      <p className="collaboration-patch-rationale">{operation.rationale}</p>
      {patch.status === "proposed" ? (
        <footer>
          <button
            className="ghost"
            disabled={disabled}
            onClick={onReject}
            type="button"
          >
            <X size={14} />
            保留原文
          </button>
          <span className="collaboration-patch-writeback">
            <LockKeyhole size={13} />
            版本修订接入后可写回
          </span>
        </footer>
      ) : null}
      {patch.status === "stale" ? (
        <p className="collaboration-patch-warning">
          <AlertTriangle size={13} />
          原文已变化，请重新选择后生成改稿。
        </p>
      ) : null}
    </section>
  )
}

function patchStatusLabel(status: ArtifactPatchCandidate["status"]) {
  return ({
    proposed: "等待处理",
    rejected: "已保留原文",
    stale: "来源已过期",
  } as const)[status]
}
