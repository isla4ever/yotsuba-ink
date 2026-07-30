import { BookOpenText, GitBranch, Tags, Users } from 'lucide-react';
import type { WorkflowStage } from '../contracts';
import { normalizeRecommendation } from './infoRecommendationModel';

type Props = {
  artifact: unknown;
  fallbackPreview: string;
  stage: WorkflowStage;
};

export function InfoCandidateSummary({ artifact, fallbackPreview, stage }: Props) {
  const recommendation = normalizeRecommendation(JSON.stringify(artifact ?? {}), stage);
  if (!recommendation.selected_title && !recommendation.synopsis) {
    return <div className="candidate-stream-copy"><p>{fallbackPreview || '候选生成中...'}</p></div>;
  }
  return (
    <div className="info-candidate-summary">
      <div className="info-candidate-title">
        <BookOpenText size={15} />
        <strong>{recommendation.selected_title || '未命名候选'}</strong>
      </div>
      <div className="info-candidate-alternates">
        {recommendation.title_candidates.slice(0, 3).map((title) => <span key={title}>{title}</span>)}
      </div>
      <p>{recommendation.synopsis || fallbackPreview}</p>
      <div className="info-candidate-metrics">
        <span><Users size={13} />{recommendation.characters.length} 人</span>
        <span><GitBranch size={13} />{recommendation.relationships.length} 组关系</span>
        <span><Tags size={13} />{recommendation.tags.length} 标签</span>
      </div>
      <div className="info-candidate-tags">
        {recommendation.tags.slice(0, 5).map((tag) => <span key={tag}>{tag}</span>)}
      </div>
    </div>
  );
}
