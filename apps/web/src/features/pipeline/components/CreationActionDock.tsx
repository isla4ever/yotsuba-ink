import { Gauge, Layers3, LoaderCircle, Pause, Play, Zap } from 'lucide-react';
import type { QualityMode } from '../types/workflow';

type Props = {
  disabled: boolean;
  paused: boolean;
  qualityMode: QualityMode;
  running: boolean;
  onPause: () => void;
  onQualityModeChange: (mode: QualityMode) => void;
  onRun: () => void;
};

export function CreationActionDock({ disabled, paused, qualityMode, running, onPause, onQualityModeChange, onRun }: Props) {
  return (
    <div className={`creation-action-dock mode-${qualityMode}${disabled ? ' locked' : ''}`}>
      <QualityModeTabs disabled={disabled} value={qualityMode} onChange={onQualityModeChange} />
      {running ? (
        <button className="run-button tech-button pause-button compact-run-action" onClick={onPause} disabled={paused} title="在下一个安全点暂停">
          <Pause size={15} />{paused ? '已暂停' : '暂停'}
        </button>
      ) : null}
      <button
        aria-label={running ? '创作中' : '开始创作'}
        className={running ? 'run-button tech-button running compact-run-action primary icon-only-run' : 'run-button tech-button compact-run-action primary icon-only-run'}
        onClick={onRun}
        disabled={running}
        title={running ? '创作中' : '开始创作'}
      >
        {running ? <LoaderCircle size={17} /> : <Play size={17} />}
      </button>
    </div>
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
