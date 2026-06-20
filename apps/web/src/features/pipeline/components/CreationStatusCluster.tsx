import { Gauge, Layers3, Zap } from 'lucide-react';
import { StageProgressNavigator } from './StageProgressNavigator';
import type { QualityMode, RunEvent, WorkflowStage } from '../types/workflow';

type Props = {
  disabled: boolean;
  events: RunEvent[];
  qualityMode: QualityMode;
  selectedStage: WorkflowStage;
  onQualityModeChange: (mode: QualityMode) => void;
};

export function CreationStatusCluster({ disabled, events, qualityMode, selectedStage, onQualityModeChange }: Props) {
  return (
    <section className={`creation-status-cluster mode-${qualityMode}${disabled ? ' locked' : ''}`}>
      <StageProgressNavigator stage={selectedStage} events={events} />
      <QualityModeTabs disabled={disabled} value={qualityMode} onChange={onQualityModeChange} />
    </section>
  );
}

function QualityModeTabs({ value, disabled, onChange }: { value: QualityMode; disabled: boolean; onChange: (mode: QualityMode) => void }) {
  const items: Array<{ key: QualityMode; label: string; hint: string; icon: typeof Zap }> = [
    { key: 'fast', label: '快', hint: '极速预览', icon: Zap },
    { key: 'balanced', label: '稳', hint: '平衡创作', icon: Gauge },
    { key: 'deep', label: '精', hint: '深度精修', icon: Layers3 },
  ];
  return (
    <div className={`quality-mode-tabs ${value}${disabled ? ' locked' : ''}`} title={disabled ? '创作中模式已锁定；暂停到安全点后可切换。' : '质量 / Token 模式'}>
      <span className="mode-glow" />
      {items.map((item) => {
        const Icon = item.icon;
        return (
          <button className={value === item.key ? 'active' : ''} disabled={disabled} key={item.key} onClick={() => onChange(item.key)} type="button" title={item.hint}>
            <Icon size={12} />
            <strong>{item.label}</strong>
          </button>
        );
      })}
    </div>
  );
}
