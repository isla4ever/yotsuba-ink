import { AlertTriangle, CircleStop } from 'lucide-react';
import type { CollaborationTurn } from "../../contracts/authorCollaboration"

type Props = {
  turn: CollaborationTurn;
};

export function CollaborationTurnOutcome({ turn }: Props) {
  if (turn.status === 'cancelled') {
    return (
      <div className="collaboration-turn-outcome cancelled" role="status">
        <CircleStop size={13} />
        <span>本轮已停止，未产生可应用内容。</span>
      </div>
    );
  }
  if (turn.status === 'contract_rejected') {
    return (
      <div className="collaboration-turn-outcome failed" role="alert">
        <AlertTriangle size={13} />
        <span>模型已返回，但内容未通过协作合同校验；本轮没有写入作品。</span>
      </div>
    );
  }
  if (turn.status === 'failed') {
    return (
      <div className="collaboration-turn-outcome failed" role="alert">
        <AlertTriangle size={13} />
        <span>{turn.error?.code === 'provider_outcome_unknown'
          ? '服务重启前未能确认模型结果；为避免重复计费，本轮没有自动重试。'
          : '本轮生成失败，作品内容未发生变化。'}</span>
      </div>
    );
  }
  return null;
}
