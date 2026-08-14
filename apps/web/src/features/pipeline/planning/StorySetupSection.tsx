import { StoryBriefFields } from '../brief/StoryBriefFields';
import { NarrativeProfilePicker } from '../brief/NarrativeProfilePicker';
import type { QualityMode, WorkflowStage } from '../contracts';
import { updateStageInputDefault } from '../lib/stageConfig';

type Props = {
  stage?: WorkflowStage;
  qualityMode?: QualityMode;
  onChange: (stage: WorkflowStage) => void;
};

export function StorySetupSection({ stage, qualityMode, onChange }: Props) {
  if (!stage) return <p className="setup-section-error" role="alert">故事起点配置缺失，当前内容未被修改。</p>;
  const narrativeProfile = String(stage.input_schema.find((field) => field.key === 'narrative_profile')?.default ?? '故事建筑师');
  return (
    <section aria-labelledby="setup-step-title-story" className="setup-form-section">
      <header>
        <p className="eyebrow">第 1 步</p>
        <h2 id="setup-step-title-story" tabIndex={-1}>先确定这本小说从哪里开始</h2>
        <p>只填写故事起点。世界规则会在创作立项定稿，角色职责、关系与弧线在下一阶段的人物圣经冻结。</p>
      </header>
      <StoryBriefFields idPrefix="setup-story" stage={stage} qualityMode={qualityMode} onChange={onChange} />
      <NarrativeProfilePicker
        value={narrativeProfile}
        onChange={(value) => onChange(updateStageInputDefault(stage, 'narrative_profile', value))}
      />
    </section>
  );
}
