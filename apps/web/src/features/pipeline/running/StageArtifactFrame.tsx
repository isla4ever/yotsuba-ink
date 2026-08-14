import { ArrowRight, CheckCheck, GitBranch, Waypoints } from 'lucide-react';
import type { StageType } from '../contracts';
import { stageArtifactFrameByType } from './stageArtifactFrameModel';

type Props = {
  stageLabel: string;
  stageType: StageType;
};

export function StageArtifactFrame({ stageLabel, stageType }: Props) {
  const frame = stageArtifactFrameByType[stageType];
  return (
    <section aria-label={`${stageLabel}产物摘要`} className={`stage-artifact-frame stage-artifact-frame-${stageType}`}>
      <div className="stage-artifact-frame-title">
        <span>本阶段产物</span>
        <strong>{frame.artifact}</strong>
      </div>
      <div>
        <Waypoints aria-hidden="true" size={14} />
        <span>请你确认</span>
        <strong>{frame.decision}</strong>
      </div>
      <div>
        <CheckCheck aria-hidden="true" size={14} />
        <span>确认后保存</span>
        <strong>{frame.writeback}</strong>
      </div>
      <div>
        <GitBranch aria-hidden="true" size={14} />
        <span>接下来会用到</span>
        <strong>{frame.downstream}</strong>
      </div>
      <ArrowRight aria-hidden="true" className="stage-artifact-frame-mark" size={15} />
    </section>
  );
}
