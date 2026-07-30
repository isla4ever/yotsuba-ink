import { Check, CircleAlert } from 'lucide-react';
import type { SetupStep, SetupStepId } from '../contracts';

type Props = {
  activeStepId: SetupStepId;
  steps: SetupStep[];
  onStepRequest: (stepId: SetupStepId) => void;
};

export function SetupStepNavigation({ activeStepId, steps, onStepRequest }: Props) {
  const activeIndex = steps.findIndex((step) => step.id === activeStepId);
  const progress = steps.length ? ((activeIndex + 1) / steps.length) * 100 : 0;

  return (
    <nav aria-label="首次准备步骤" className="setup-step-navigation">
      <div className="setup-mobile-progress">
        <strong>{activeIndex + 1}/{steps.length}</strong>
        <span>{steps.find((step) => step.id === activeStepId)?.label}</span>
      </div>
      <ol>
        {steps.map((step, index) => {
          const active = step.id === activeStepId;
          const blocked = step.issues.some((issue) => issue.severity === 'blocking');
          return (
            <li className={active ? 'active' : ''} data-status={blocked ? 'blocked' : step.status} key={step.id}>
              <button aria-current={active ? 'step' : undefined} type="button" onClick={() => onStepRequest(step.id)}>
                <span className="setup-step-marker">
                  {!blocked && step.status === 'complete' ? <Check size={14} /> : blocked ? <CircleAlert size={14} /> : index + 1}
                </span>
                <span className="setup-step-copy"><strong>{step.label}</strong><small>{step.summary}</small></span>
              </button>
          </li>
        );
      })}
      </ol>
      <div
        aria-label="首次准备进度"
        aria-valuemax={steps.length}
        aria-valuemin={1}
        aria-valuenow={activeIndex + 1}
        className="setup-progress-meter"
        role="progressbar"
      >
        <span style={{ width: `${progress}%` }} />
      </div>
    </nav>
  );
}
