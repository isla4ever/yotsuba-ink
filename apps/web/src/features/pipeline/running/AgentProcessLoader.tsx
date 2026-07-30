import { CheckCircle2 } from 'lucide-react';
import { ButtonLoadingIndicator } from '../layout/ButtonLoadingIndicator';
import { ManuscriptLoadingIndicator } from '../layout/ManuscriptLoadingIndicator';

type Props = {
  title: string;
  steps: Array<{ label: string; done: boolean; detail?: string }>;
};

export function AgentProcessLoader({ title, steps }: Props) {
  return (
    <section className="agent-process-loader">
      <div className="agent-process-orb">
        <ManuscriptLoadingIndicator size="compact" />
      </div>
      <div>
        <p className="eyebrow">生成进度</p>
        <h3>{title}</h3>
      </div>
      <div className="agent-process-steps">
        {steps.map((step) => (
          <article className={step.done ? 'done' : ''} key={step.label}>
            {step.done ? <CheckCircle2 size={14} /> : <ButtonLoadingIndicator />}
            <strong>{step.label}</strong>
            <span>{step.detail ?? (step.done ? '已完成' : '进行中')}</span>
          </article>
        ))}
      </div>
    </section>
  );
}
