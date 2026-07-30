import { AlertCircle, CheckCircle2, SlidersHorizontal } from 'lucide-react';
import { useRef, type KeyboardEvent } from 'react';
import type { InspectorTarget, WorkflowStage } from '../contracts';
import { stageLabelForUi } from '../lib/display';
import { stageConfigurationReadiness } from '../lib/planningReadiness';

type Props = {
  onOpenConfig?: () => void;
  onSelect: (target: InspectorTarget) => void;
  selectedId: string;
  stages: WorkflowStage[];
};

export function PlanningStageNavigator({ onOpenConfig, onSelect, selectedId, stages }: Props) {
  const buttonRefs = useRef<Array<HTMLButtonElement | null>>([]);

  const selectAt = (index: number) => {
    const stage = stages[index];
    if (!stage) return;
    onSelect({ kind: 'stage', id: stage.id });
    buttonRefs.current[index]?.focus();
  };

  const handleKeyDown = (event: KeyboardEvent<HTMLButtonElement>, index: number) => {
    const last = stages.length - 1;
    const nextIndex = {
      ArrowDown: Math.min(last, index + 1),
      ArrowLeft: Math.max(0, index - 1),
      ArrowRight: Math.min(last, index + 1),
      ArrowUp: Math.max(0, index - 1),
      End: last,
      Home: 0,
    }[event.key];
    if (nextIndex === undefined) return;
    event.preventDefault();
    if (nextIndex === index) return;
    selectAt(nextIndex);
  };

  return (
    <nav aria-label="创作阶段选择" className="planning-stage-nav">
      <ol className="planning-stage-list">
        {stages.map((stage, index) => {
          const active = selectedId === stage.id;
          const readiness = stageConfigurationReadiness(stage);
          const statusLabel = readiness.ready ? '配置就绪' : `待补 ${readiness.missingLabels.length} 项`;
          return (
            <li key={stage.id}>
              <button
                aria-current={active ? 'step' : undefined}
                aria-label={`第 ${index + 1} 阶段，${stageLabelForUi(stage)}，${statusLabel}`}
                className={active ? 'active' : ''}
                onClick={() => onSelect({ kind: 'stage', id: stage.id })}
                onKeyDown={(event) => handleKeyDown(event, index)}
                ref={(element) => { buttonRefs.current[index] = element; }}
                tabIndex={active ? 0 : -1}
                type="button"
              >
                <span>{String(index + 1).padStart(2, '0')}</span>
                <span className="planning-stage-nav-copy">
                  <strong>{stageLabelForUi(stage)}</strong>
                  <small>{statusLabel}</small>
                </span>
                {readiness.ready ? <CheckCircle2 size={13} /> : <AlertCircle size={13} />}
              </button>
            </li>
          );
        })}
      </ol>
      {onOpenConfig ? (
        <button aria-label="编辑当前阶段配置" className="planning-config-trigger" onClick={onOpenConfig} type="button">
          <SlidersHorizontal size={16} />
          <span>编辑当前阶段</span>
        </button>
      ) : null}
    </nav>
  );
}
