import { CheckCircle2, Circle, GitBranch, Loader2, XCircle } from 'lucide-react';
import type { RunEvent, WorkflowStage } from '../types/workflow';

type Props = {
  stages: WorkflowStage[];
  selectedId: string;
  events: RunEvent[];
  onSelect: (stage: WorkflowStage) => void;
};

export function StagePipeline({ stages, selectedId, events, onSelect }: Props) {
  return (
    <section className="pipeline-board">
      <div className="pipeline-header">
        <div>
          <p className="eyebrow">Pipeline</p>
          <h1>全自动长篇小说生成</h1>
        </div>
        <div className="pipeline-metrics">
          <span>8 阶段</span>
          <span>演示可运行</span>
          <span>Wiki 横切记忆</span>
        </div>
      </div>
      <div className="pipeline-track">
        {stages.map((stage, index) => (
          <article
            className={`stage-card ${selectedId === stage.id ? 'selected' : ''} ${statusFor(stage.id, events)}`}
            key={stage.id}
            onClick={() => onSelect(stage)}
          >
            <div className="stage-index">{String(index + 1).padStart(2, '0')}</div>
            <div className="stage-main">
              <div className="stage-title-row">
                <StatusIcon status={statusFor(stage.id, events)} />
                <strong>{stage.label}</strong>
              </div>
              <p>{stage.type}</p>
              <div className="stage-tags">
                <span>{stage.provider_profile_id}</span>
                <span>{stage.memory_policy.read ? '读记忆' : '不读记忆'}</span>
                <span>{stage.memory_policy.write ? '写回' : '不写回'}</span>
              </div>
            </div>
            {index < stages.length - 1 ? <GitBranch className="stage-connector" size={18} /> : null}
          </article>
        ))}
      </div>
    </section>
  );
}

function statusFor(stageId: string, events: RunEvent[]) {
  const latest = events.find((event) => event.node_id === stageId && event.type.startsWith('node_'));
  if (!latest) return 'idle';
  if (latest.type === 'node_started') return 'running';
  if (latest.type === 'node_completed') return 'done';
  if (latest.type === 'node_failed') return 'failed';
  return 'idle';
}

function StatusIcon({ status }: { status: string }) {
  if (status === 'running') return <Loader2 className="spin" size={16} />;
  if (status === 'done') return <CheckCircle2 size={16} />;
  if (status === 'failed') return <XCircle size={16} />;
  return <Circle size={16} />;
}
