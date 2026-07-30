import { StoryBriefFields } from '../brief/StoryBriefFields';
import type { WorkflowStage } from '../contracts';

type Props = {
  stage?: WorkflowStage;
  onChange: (stage: WorkflowStage) => void;
};

export function StorySetupSection({ stage, onChange }: Props) {
  if (!stage) return <p className="setup-section-error" role="alert">故事起点配置缺失，当前内容未被修改。</p>;
  return (
    <section aria-labelledby="setup-step-title-story" className="setup-form-section">
      <header>
        <p className="eyebrow">第 1 步</p>
        <h2 id="setup-step-title-story" tabIndex={-1}>先确定这本小说从哪里开始</h2>
        <p>只填写立项所需的信息。人物、关系和完整世界观会在信息推荐阶段生成后由你定稿。</p>
      </header>
      <StoryBriefFields idPrefix="setup-story" stage={stage} onChange={onChange} />
    </section>
  );
}
