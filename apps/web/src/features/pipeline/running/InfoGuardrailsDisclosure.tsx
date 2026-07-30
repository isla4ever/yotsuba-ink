import { ShieldCheck } from 'lucide-react';
import type { InfoRecommendation } from './infoRecommendationModel';

type Props = {
  readOnly: boolean;
  recommendation: InfoRecommendation;
  onChange: (patch: Partial<InfoRecommendation>) => void;
};

export function InfoGuardrailsDisclosure({ onChange, readOnly, recommendation }: Props) {
  const constraintCount = recommendation.downstream_constraints.length;
  const riskCount = recommendation.risk_notes.length;
  return (
    <details className="info-guardrails-disclosure">
      <summary>
        <span><ShieldCheck size={15} />后续创作边界</span>
        <b>{constraintCount} 条约束 · {riskCount} 条风险</b>
      </summary>
      <div className="info-guardrails-fields">
        <label>
          <span>下游约束</span>
          <textarea
            aria-label="下游创作约束，每行一条"
            placeholder={readOnly ? '' : '每行一条，供梗概、大纲、细纲和正文继承'}
            readOnly={readOnly}
            value={recommendation.downstream_constraints.join('\n')}
            onChange={(event) => onChange({ downstream_constraints: lines(event.target.value) })}
          />
        </label>
        <label>
          <span>风险提示</span>
          <textarea
            aria-label="创作风险提示，每行一条"
            placeholder={readOnly ? '' : '每行一条，用于后续质量检查'}
            readOnly={readOnly}
            value={recommendation.risk_notes.join('\n')}
            onChange={(event) => onChange({ risk_notes: lines(event.target.value) })}
          />
        </label>
      </div>
    </details>
  );
}

function lines(value: string) {
  return value.split(/\r?\n/).map((item) => item.trim()).filter(Boolean);
}
