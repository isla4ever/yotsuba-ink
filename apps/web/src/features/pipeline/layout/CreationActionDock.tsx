import type { QualityMode } from '../contracts';
import { qualityModeProfiles } from '../lib/qualityModes';
import type { ModeRevealOrigin } from './modeRevealTransition';
import { useRunStateContext, useWorkflowConfigContext, useUICommandContext } from '../state/pipelineShellContext';
import { runActionPresentation } from '../state/runPresentationState';
import { AnimatePresence, motion } from 'motion/react';
import { CheckCircle2, Clock3, CornerUpLeft, Play, type LucideIcon } from 'lucide-react';
import { ButtonLoadingIndicator } from './ButtonLoadingIndicator';

type Props = {
  /** Mode-switch lock computed by the header (owns the transition notice). */
  disabled: boolean;
  onQualityModeChange: (mode: QualityMode, origin?: ModeRevealOrigin) => void;
};

type RunButtonIconState = {
  Icon: LucideIcon;
  key: string;
  size: number;
};

export function CreationActionDock({ disabled, onQualityModeChange }: Props) {
  const run = useRunStateContext();
  const { qualityMode } = useWorkflowConfigContext();
  const { runPrimaryAction } = useUICommandContext();
  const action = runActionPresentation({
    approvalPending: run.approvalPending,
    checkpointContinueReady: run.checkpointContinueReady,
    briefContinueReady: run.briefContinueReady,
    qualityMode,
    runControlState: run.runControlState,
    running: run.running,
    selectedStageCheckpointReady: Boolean(run.stageRuntimes[run.selectedStage.id]?.checkpointReady),
    selectedStageStatus: run.stageRuntimes[run.selectedStage.id]?.status ?? 'idle',
    selectedStageType: run.selectedStage.type,
    transitioning: run.transitioning,
    workspacePhase: run.workspacePhase,
  });
  const loading = action.key === 'running-locked';
  const iconState: RunButtonIconState = action.key === 'awaiting-confirmation'
      ? { Icon: Clock3, key: 'awaiting', size: 16 }
      : action.key === 'return'
        ? { Icon: CornerUpLeft, key: 'return', size: 17 }
        : action.key === 'continue' || action.key === 'resume'
          ? { Icon: CheckCircle2, key: 'continue', size: 17 }
          : { Icon: Play, key: 'start', size: 17 };
  const RunIcon = iconState.Icon;
  return (
    <div className={`creation-action-dock mode-${qualityMode} state-${action.visualState}${disabled ? ' locked' : ''}`}>
      <QualityModeTabs disabled={disabled} value={qualityMode} onChange={onQualityModeChange} />
      <button
        aria-busy={action.key === 'running-locked'}
        aria-label={action.label}
        className={`run-button tech-button compact-run-action header-run-action ${action.visualState}`}
        disabled={action.disabled}
        onClick={runPrimaryAction}
        title={action.title}
      >
        <span aria-hidden="true" className="run-button-icon-slot">
          <AnimatePresence initial={false}>
            <motion.span
              animate={{ opacity: 1, rotate: 0, scale: 1 }}
              className="run-button-icon-motion"
              exit={{ opacity: 0, rotate: 5, scale: 0.9 }}
              initial={{ opacity: 0, rotate: -5, scale: 0.9 }}
              key={iconState.key}
              transition={{ duration: 0.085, ease: [0.2, 0.8, 0.2, 1] }}
            >
              {loading ? <ButtonLoadingIndicator size="medium" /> : <RunIcon size={iconState.size} />}
            </motion.span>
          </AnimatePresence>
        </span>
        <span className="run-button-label">{action.label}</span>
      </button>
    </div>
  );
}

function QualityModeTabs({ value, disabled, onChange }: { value: QualityMode; disabled: boolean; onChange: (mode: QualityMode, origin?: ModeRevealOrigin) => void }) {
  const items: Array<{ key: QualityMode }> = [
    { key: 'fast' },
    { key: 'balanced' },
    { key: 'deep' },
  ];
  return (
    <div aria-label="创作模式" className={`quality-mode-tabs ${value}${disabled ? ' locked' : ''}`} role="group" title={disabled ? '本次运行模式已锁定；完成并回到配置态后可切换下一次运行。' : '创作模式'}>
      <span className="mode-glow" />
      {items.map((item) => {
        const profile = qualityModeProfiles[item.key];
        const Icon = profile.icon;
        return (
          <button
            aria-label={profile.title}
            aria-pressed={value === item.key}
            className={value === item.key ? 'active' : ''}
            disabled={disabled}
            key={item.key}
            onClick={(event) => {
              // Radial-reveal origin: pointer position, or the button center for
              // keyboard activation (clientX/Y are 0 there).
              const rect = event.currentTarget.getBoundingClientRect();
              const origin = event.clientX || event.clientY
                ? { x: event.clientX, y: event.clientY }
                : { x: rect.left + rect.width / 2, y: rect.top + rect.height / 2 };
              onChange(item.key, origin);
            }}
            type="button"
            title={`${profile.title} · ${profile.intervention}`}
          >
            <Icon size={12} />
            <strong>{profile.shortLabel}</strong>
          </button>
        );
      })}
    </div>
  );
}
