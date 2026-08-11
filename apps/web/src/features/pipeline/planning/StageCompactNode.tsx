import { Handle, Position, type NodeProps } from '@xyflow/react';
import { AlertCircle, CheckCircle2, Circle, CirclePause, Database, FileText, ShieldCheck, Sparkles, XCircle } from 'lucide-react';
import { useEffect, useMemo, useState } from 'react';
import type { RunEvent, WorkflowStage } from '../contracts';
import { ButtonLoadingIndicator } from '../layout/ButtonLoadingIndicator';
import { modelNameForUi, providerNameForUi, stageLabelForUi } from '../lib/display';
import { stageArtifactLabel, stageConfigurationReadiness } from '../lib/planningReadiness';
import { runtimeElapsedSeconds, type NodeRuntimeState } from './cockpitRuntime';

export type StageNodeData = {
  stage: WorkflowStage;
  index: number;
  selected: boolean;
  status: string;
  events: RunEvent[];
  presentation?: 'planning' | 'runtime';
  runtime?: NodeRuntimeState;
};

export function StageCompactNode({ data }: NodeProps) {
  const nodeData = data as unknown as StageNodeData;
  const { stage, index, selected, status, events, presentation = 'runtime', runtime } = nodeData;
  const completed = events.some((event) => event.type === 'artifact.committed' && event.stage_id === stage.id);
  const memoryRead = events.some((event) => event.type === 'evidence.proposed' && event.stage_id === stage.id);
  const memoryWrite = events.some((event) => event.type === 'writeback.committed' && event.stage_id === stage.id);
  const reviewed = events.some((event) => event.type === 'review.completed' && event.stage_id === stage.id);
  const elapsedLabel = useStageElapsedLabel(events, stage.id, status, runtime);
  const readiness = stageConfigurationReadiness(stage);

  return (
    <article className={`compact-node ${presentation === 'planning' ? 'planning-node' : ''} ${selected ? 'selected' : ''} ${status}`}>
      <Handle id="top" type="target" position={Position.Top} />
      <Handle id="left" type="target" position={Position.Left} />
      <Handle id="right-target" type="target" position={Position.Right} />
      <div className="compact-node-top">
        <span className="node-index">{String(index + 1).padStart(2, '0')}</span>
        <StatusIcon status={status} />
        <strong>{stageLabelForUi(stage)}</strong>
      </div>
      {presentation === 'planning' ? (
        <>
          <div className="node-planning-artifact"><FileText size={12} /><span>{stageArtifactLabel(stage)}</span></div>
          <div className={`node-planning-readiness ${readiness.ready ? 'ready' : 'incomplete'}`}>
            {readiness.ready ? <CheckCircle2 size={12} /> : <AlertCircle size={12} />}
            <span>{readiness.ready ? '配置就绪' : `待补 ${readiness.missingLabels.length} 项`}</span>
            <em>{readiness.total ? `${readiness.completed}/${readiness.total} 必填` : '无必填项'}</em>
          </div>
        </>
      ) : (
        <>
          <div className="node-meta">
            <span>{providerNameForUi(stage.provider_profile_id)}</span>
            <span>{modelNameForUi(stage.model_settings.model)}</span>
            <span className={`node-timer ${status}`}>{elapsedLabel}</span>
          </div>
          <div className="node-badges">
            <span className={memoryRead ? 'on' : ''}><Database size={12} />读</span>
            <span className={memoryWrite ? 'on' : ''}><Database size={12} />写</span>
            <span className={reviewed ? 'on' : ''}><ShieldCheck size={12} />{reviewed ? '已审稿' : '待审稿'}</span>
            <span className={completed ? 'on' : ''}><FileText size={12} />{completed ? '产物' : '待产物'}</span>
          </div>
        </>
      )}
      <Handle id="bottom" type="target" position={Position.Bottom} />
      <Handle id="bottom-source" type="source" position={Position.Bottom} />
      <Handle id="right" type="source" position={Position.Right} />
    </article>
  );
}

function useStageElapsedLabel(events: RunEvent[], stageId: string, status: string, runtime?: NodeRuntimeState) {
  const startKey = useMemo(() => {
    const start = events.find((event) => event.type === 'node.started' && event.stage_id === stageId);
    return runtime?.startKey || (start ? `${start.run_id}-${start.event_id}` : '');
  }, [events, runtime?.startKey, stageId]);
  const completedSeconds = runtime?.completedSeconds ?? null;
  const [tick, setTick] = useState(0);

  useEffect(() => {
    setTick(0);
    if (status !== 'running' || !startKey) return;
    const timer = window.setInterval(() => setTick((value) => value + 1), 1000);
    return () => window.clearInterval(timer);
  }, [startKey, status]);

  if (status === 'running') return `${runtime ? runtimeElapsedSeconds(runtime) ?? Math.max(1, tick + 1) : Math.max(1, tick + 1)}s`;
  if (status === 'awaiting') return '待决策';
  if (status === 'done' && completedSeconds) return `${completedSeconds}s`;
  if (status === 'failed') return '失败';
  return '待机';
}

function StatusIcon({ status }: { status: string }) {
  if (status === 'running') return <ButtonLoadingIndicator />;
  if (status === 'awaiting') return <CirclePause size={14} />;
  if (status === 'done') return <CheckCircle2 size={14} />;
  if (status === 'failed') return <XCircle size={14} />;
  return <Circle size={14} />;
}

export function CrosscuttingNode({ data }: NodeProps) {
  const nodeData = data as unknown as { compact?: boolean; disabled?: boolean; kind: 'wiki' | 'quality'; title: string; subtitle: string; selected?: boolean };
  const isWiki = nodeData.kind === 'wiki';
  return (
    <article
      aria-disabled={nodeData.disabled || undefined}
      className={`crosscutting-node ${nodeData.kind}${nodeData.compact ? ' compact' : ''}${nodeData.selected ? ' selected' : ''}${nodeData.disabled ? ' disabled' : ''}`}
    >
      <Handle id={isWiki ? 'bottom' : 'top'} type="source" position={isWiki ? Position.Bottom : Position.Top} />
      <Handle id="left" type="source" position={Position.Left} />
      <Handle id="right" type="source" position={Position.Right} />
      <div className="crosscutting-node-body">
        <div className="crosscutting-orb">
          {isWiki ? <Database size={18} /> : <ShieldCheck size={18} />}
        </div>
        <div className="crosscutting-copy">
          <strong>{nodeData.title}</strong>
          <span>{nodeData.subtitle}</span>
        </div>
        <Sparkles size={14} className="crosscutting-spark" />
      </div>
    </article>
  );
}
