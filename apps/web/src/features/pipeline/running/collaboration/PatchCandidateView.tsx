import { AlertTriangle, Check, RotateCcw, X } from 'lucide-react';
import type { ArtifactPatchCandidate } from "../../contracts/authorCollaboration"

type Props = {
  before: string;
  disabled: boolean;
  onAccept: () => void;
  onReject: () => void;
  patch: ArtifactPatchCandidate;
};

export function PatchCandidateView({ before, disabled, onAccept, onReject, patch }: Props) {
  const operation = patch.operations[0];
  if (!operation) return null;
  return (
    <section className="collaboration-patch" data-status={patch.status}>
      <header>
        <div><RotateCcw size={14} /><strong>改稿候选</strong></div>
        <span>{patchStatusLabel(patch.status)}</span>
      </header>
      <div className="collaboration-patch-diff">
        <div><span>原文</span><p>{before}</p></div>
        <div><span>建议稿</span><p>{operation.replacement}</p></div>
      </div>
      <p className="collaboration-patch-rationale">{operation.rationale}</p>
      {patch.status === 'proposed' ? (
        <footer>
          <button className="ghost" disabled={disabled} onClick={onReject} type="button"><X size={14} />保留原文</button>
          <button className="primary" disabled={disabled} onClick={onAccept} type="button"><Check size={14} />应用到当前稿</button>
        </footer>
      ) : null}
      {patch.status === 'stale' ? <p className="collaboration-patch-warning"><AlertTriangle size={13} />原文已变化，请重新选择后生成改稿。</p> : null}
    </section>
  );
}

function patchStatusLabel(status: ArtifactPatchCandidate['status']) {
  return ({ proposed: '等待决定', accepted: '已应用', rejected: '已保留原文', stale: '来源已过期' } as const)[status];
}
