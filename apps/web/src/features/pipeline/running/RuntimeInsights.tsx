import { AnimatePresence, motion } from 'motion/react';
import type { WorkflowStage } from '../contracts';
import { routeMotionVariants } from '../lib/motion';
import { RuntimeCompactTile, RuntimeInsightPanel, type RuntimeInsightContext } from './RuntimeInsightPanel';
import type { RuntimePanelKey } from './stageRuntimeLayout';

type Props = RuntimeInsightContext & {
  activeStage: WorkflowStage;
  compactPanelKeys: readonly RuntimePanelKey[];
  panelKeys: readonly RuntimePanelKey[];
  visible: boolean;
  onEditInfo: (target: 'worldbuilding' | 'character') => void;
  onOpenPanel: (panel: RuntimePanelKey) => void;
};

export function RuntimeInsights({
  activeStage,
  compactPanelKeys,
  panelKeys,
  visible,
  onEditInfo,
  onOpenPanel,
  ...context
}: Props) {
  return (
    <AnimatePresence>
      {visible ? (
        <motion.aside
          animate="animate"
          aria-label={panelKeys.length ? '阶段运行面板' : '阶段上下文入口'}
          className={`stage-run-side panels-${panelKeys.length} stage-${activeStage.type}${panelKeys.length === 0 ? ' context-rail' : ''}`}
          exit="exit"
          initial="initial"
          variants={routeMotionVariants}
        >
          {panelKeys.map((panel) => (
            <RuntimeInsightPanel
              {...context}
              key={panel}
              panel={panel}
              onEditInfo={activeStage.type === 'info_recommend' ? onEditInfo : undefined}
            />
          ))}
          {compactPanelKeys.length ? (
            <div className="runtime-context-rail">
              <div className="runtime-context-rail-label" aria-hidden="true">
                <span>阶段上下文</span>
                <small>按需查看，不占用稿件主体</small>
              </div>
              <div className="runtime-compact-tile-grid">
                {compactPanelKeys.map((panel) => (
                  <RuntimeCompactTile
                    characterGraphOverride={context.characterGraphOverride}
                    detailWritebacks={context.detailWritebacks}
                    events={context.events}
                    key={panel}
                    memoryEvents={context.memoryEvents}
                    outlineWritebacks={context.outlineWritebacks}
                    panel={panel}
                    summaryWritebacks={context.summaryWritebacks}
                    workflow={context.workflow}
                    onOpen={() => onOpenPanel(panel)}
                  />
                ))}
              </div>
            </div>
          ) : null}
        </motion.aside>
      ) : null}
    </AnimatePresence>
  );
}
