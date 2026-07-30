import { ReferenceResearchPanel } from '../brief/ReferenceResearchPanel';
import type { KnowledgeDocument, WorkflowStage } from '../contracts';

type Props = {
  stage?: WorkflowStage;
  knowledgeDocuments: KnowledgeDocument[];
  onChange: (stage: WorkflowStage) => void;
  onOpenKnowledgeManager: () => void;
};

/**
 * Phase 12 A4: no longer a standalone guided-setup step — this is the expanded
 * body of the 确认启动 reference card (smart_search applied by default).
 */
export function ReferenceSetupSection({ stage, knowledgeDocuments, onChange, onOpenKnowledgeManager }: Props) {
  if (!stage) return <p className="setup-section-error" role="alert">参考方式配置缺失，当前内容未被修改。</p>;
  return (
    <>
      <p className="setup-reference-intro">参考资料是可选项。没有资料也可以直接开始，系统会仅依据你的故事设定创作。</p>
      <ReferenceResearchPanel
        knowledgeDocuments={knowledgeDocuments}
        stage={stage}
        onChange={onChange}
        onOpenKnowledgeManager={onOpenKnowledgeManager}
      />
    </>
  );
}
