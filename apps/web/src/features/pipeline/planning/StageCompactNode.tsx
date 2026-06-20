import { Handle, Position, type NodeProps } from '@xyflow/react';
import { CheckCircle2, Circle, Database, FileText, Loader2, ShieldCheck, Sparkles, XCircle } from 'lucide-react';
import type { QualityEvent, RunEvent, WorkflowStage } from '../contracts';
import { modelNameForUi, providerNameForUi } from '../lib/display';

export type StageNodeData = {
  stage: WorkflowStage;
  index: number;
  selected: boolean;
  status: string;
  quality?: QualityEvent;
  events: RunEvent[];
};

export function StageCompactNode({ data }: NodeProps) {
  const nodeData = data as unknown as StageNodeData;
  const { stage, index, selected, status, quality, events } = nodeData;
  const completed = events.some((event) => event.type === 'node_completed' && event.node_id === stage.id);
  const memoryRead = events.some((event) => event.type === 'memory_context_loaded' && event.node_id === stage.id);
  const memoryWrite = events.some((event) => event.type === 'memory_writeback_completed' && event.node_id === stage.id);

  return (
    <article className={`compact-node ${selected ? 'selected' : ''} ${status}`}>
      <Handle id="top" type="target" position={Position.Top} />
      <Handle id="left" type="target" position={Position.Left} />
      <Handle id="right-target" type="target" position={Position.Right} />
      <div className="compact-node-top">
        <span className="node-index">{String(index + 1).padStart(2, '0')}</span>
        <StatusIcon status={status} />
        <strong>{stage.label}</strong>
      </div>
      <div className="node-meta">
        <span>{providerNameForUi(stage.provider_profile_id)}</span>
        <span>{modelNameForUi(stage.model_settings.model)}</span>
      </div>
      <div className="node-badges">
        <span className={memoryRead ? 'on' : ''}><Database size={12} />读</span>
        <span className={memoryWrite ? 'on' : ''}><Database size={12} />写</span>
        <span className={quality?.passed ? 'on' : quality ? 'warn' : ''}><ShieldCheck size={12} />{quality ? quality.score.toFixed(2) : stage.quality_policy.min_score.toFixed(2)}</span>
        <span className={completed ? 'on' : ''}><FileText size={12} />{completed ? '产物' : '待产物'}</span>
      </div>
      <Handle id="bottom" type="source" position={Position.Bottom} />
      <Handle id="right" type="source" position={Position.Right} />
    </article>
  );
}

function StatusIcon({ status }: { status: string }) {
  if (status === 'running') return <Loader2 className="spin" size={14} />;
  if (status === 'done') return <CheckCircle2 size={14} />;
  if (status === 'failed') return <XCircle size={14} />;
  return <Circle size={14} />;
}

export function CrosscuttingNode({ data }: NodeProps) {
  const nodeData = data as unknown as { kind: 'wiki' | 'quality'; title: string; subtitle: string; selected?: boolean };
  return (
    <article className={`crosscutting-node ${nodeData.kind}${nodeData.selected ? ' selected' : ''}`}>
      <Handle id="left" type="source" position={Position.Left} />
      <Handle id="right" type="source" position={Position.Right} />
      <div className="crosscutting-orb">
        {nodeData.kind === 'wiki' ? <Database size={18} /> : <ShieldCheck size={18} />}
      </div>
      <div>
        <strong>{nodeData.title}</strong>
        <span>{nodeData.subtitle}</span>
      </div>
      <Sparkles size={14} className="crosscutting-spark" />
    </article>
  );
}
