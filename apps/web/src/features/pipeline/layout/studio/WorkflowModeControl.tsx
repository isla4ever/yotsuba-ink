import { Gauge, Scale, Sparkles } from 'lucide-react';
import type { QualityMode } from '../../contracts';

type Props = {
  readOnly?: boolean;
  value: QualityMode;
  onChange: (mode: QualityMode) => void;
};

const modes = [
  { id: 'fast', label: '极速', Icon: Gauge },
  { id: 'balanced', label: '平衡', Icon: Scale },
  { id: 'deep', label: '精细', Icon: Sparkles },
] as const;

export function WorkflowModeControl({ readOnly = false, value, onChange }: Props) {
  return (
    <section aria-labelledby="workflow-mode-title" className="workflow-mode-control">
      <header>
        <h2 id="workflow-mode-title">创作模式</h2>
        <span>{readOnly ? '官方配置' : '审核与模型策略'}</span>
      </header>
      <div aria-label="创作模式" className="workflow-mode-segments" role="radiogroup">
        {modes.map(({ id, label, Icon }) => (
          <button
            aria-checked={value === id}
            disabled={readOnly}
            key={id}
            onClick={() => onChange(id)}
            role="radio"
            type="button"
          >
            <Icon aria-hidden="true" size={14} />
            <span>{label}</span>
          </button>
        ))}
      </div>
    </section>
  );
}
