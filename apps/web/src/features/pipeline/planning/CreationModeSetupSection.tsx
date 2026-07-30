import { Check } from 'lucide-react';
import type { QualityMode } from '../contracts';
import { qualityModeProfiles } from '../lib/qualityModes';

type Props = {
  /**
   * settings — 设置对话框内的模式编辑区（带标题）。
   * review — 确认启动页创作模式卡的展开态（Phase 12 A4，仅选项列表）。
   */
  context?: 'settings' | 'review';
  value: QualityMode;
  onChange: (mode: QualityMode) => void;
};

const modes: QualityMode[] = ['fast', 'balanced', 'deep'];

export function CreationModeSetupSection({ context = 'review', value, onChange }: Props) {
  const titleId = `${context}-step-title-creation-mode`;
  return (
    <section aria-label={context === 'review' ? '创作模式' : undefined} aria-labelledby={context === 'settings' ? titleId : undefined} className="setup-form-section" id={`${context}-quality-mode`}>
      {context === 'settings' ? (
        <header>
          <p className="eyebrow">创作控制</p>
          <h2 id={titleId} tabIndex={-1}>修改创作模式</h2>
          <p>这里决定自动推进范围和人工定稿点，不改变故事设定，也不会在切换时创建运行。</p>
        </header>
      ) : null}
      <div aria-label="创作模式" className="setup-mode-options" role="radiogroup">
        {modes.map((mode) => {
          const profile = qualityModeProfiles[mode];
          const Icon = profile.icon;
          const selected = value === mode;
          return (
            <button
              aria-checked={selected}
              className={selected ? 'selected' : ''}
              id={`${context}-quality-mode-${mode}`}
              key={mode}
              role="radio"
              type="button"
              onClick={() => onChange(mode)}
            >
              <span className="setup-mode-icon"><Icon size={18} /></span>
              <span><strong>{profile.title}</strong><small>{profile.intervention} · {profile.useCase}</small></span>
              <p>{profile.description}</p>
              {selected ? <Check className="setup-mode-check" size={16} /> : null}
            </button>
          );
        })}
      </div>
    </section>
  );
}
