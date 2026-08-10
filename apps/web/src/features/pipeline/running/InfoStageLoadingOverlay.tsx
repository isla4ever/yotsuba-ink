import { Check, Circle } from 'lucide-react';
import type { RunEvent } from '../contracts';
import { ButtonLoadingIndicator } from '../layout/ButtonLoadingIndicator';
import { LoadingOverlay } from '../layout/LoadingOverlay';
import { infoStageLoadingCopy, infoStageLoadingMilestones } from './infoStageLoadingState';

type Props = {
  events: RunEvent[];
  visible: boolean;
};

export function InfoStageLoadingOverlay({ events, visible }: Props) {
  const copy = infoStageLoadingCopy(events);
  const milestones = infoStageLoadingMilestones(events);
  return (
    <LoadingOverlay
      className="info-stage-loading-overlay"
      detail={copy.detail}
      eyebrow="创作立项"
      open={visible}
      title={copy.title}
    >
      <ol className="info-loading-milestones">
        {milestones.map((milestone) => (
          <li className={milestone.complete ? 'complete' : milestone.current ? 'current' : ''} key={milestone.label}>
            {milestone.complete ? <Check size={13} /> : milestone.current ? <ButtonLoadingIndicator /> : <Circle size={11} />}
            <span>{milestone.label}</span>
          </li>
        ))}
      </ol>
    </LoadingOverlay>
  );
}
