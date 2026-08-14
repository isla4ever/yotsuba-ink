import { AlertTriangle, Check, CircleDashed, Hourglass, Settings2 } from 'lucide-react';
import type { RunEvent, WorkflowDefinition } from '../contracts';
import { ButtonLoadingIndicator } from '../layout/ButtonLoadingIndicator';
import { buildArtifactDeckItems, buildPlanningStagePosition, type ArtifactDeckStatus } from './artifactDeckModel';

type Props = {
  workflow: WorkflowDefinition;
  events: RunEvent[];
  /** Stage highlighted as the pipeline focus (active during runs, selected before). */
  activeStageId: string;
  runHasStarted: boolean;
  onSelectStage: (stageId: string) => void;
};

/**
 * The cockpit's left pipeline: a condensed vertical stepper (dot + connector
 * line per stage) in the build-page tradition — always fully visible, never a
 * clipped card deck. Click opens stage config before the run and the stage
 * detail dialog during it.
 */
export function CockpitPipelineRail({ activeStageId, events, onSelectStage, runHasStarted, workflow }: Props) {
  const items = buildArtifactDeckItems(workflow, events, activeStageId);
  const position = buildPlanningStagePosition(workflow, events, activeStageId);
  return (
    <nav aria-label="创作流水线" className="cockpit-pipeline-rail">
      <header className="cockpit-rail-head">
        <div>
          <p className="eyebrow">创作流程</p>
          <h2>八阶段流水线</h2>
        </div>
        <span className="cockpit-rail-position">
          {position.completed ? `${position.completed}/${position.total} 完成` : `${position.total} 阶段`}
        </span>
      </header>
      <ol className="cockpit-rail-steps">
        {items.map((item, index) => (
          <li className={`rail-step status-${item.status} ${item.id === activeStageId ? 'is-active' : ''}`} key={item.id}>
            <button
              aria-current={item.id === activeStageId ? 'step' : undefined}
              onClick={() => onSelectStage(item.id)}
              title={runHasStarted ? `查看${item.label}详情` : `配置${item.label}`}
              type="button"
            >
              <span className="rail-step-track">
                <span className="rail-step-dot"><StepGlyph status={item.status} /></span>
                {index < items.length - 1 ? <span aria-hidden className="rail-step-line" /> : null}
              </span>
              <span className="rail-step-copy">
                <span className="rail-step-title">
                  <strong>{item.label}</strong>
                  <em>{item.statusLabel}</em>
                </span>
                <small>{item.artifact}</small>
              </span>
              {!runHasStarted ? <span className="rail-step-config"><Settings2 size={13} /></span> : null}
            </button>
          </li>
        ))}
      </ol>
    </nav>
  );
}

function StepGlyph({ status }: { status: ArtifactDeckStatus }) {
  if (status === 'confirmed') return <Check size={12} strokeWidth={3} />;
  if (status === 'running') return <ButtonLoadingIndicator />;
  if (status === 'awaiting') return <Hourglass size={11} />;
  if (status === 'attention') return <AlertTriangle size={11} />;
  return <CircleDashed size={11} />;
}
