import { AnimatePresence, motion } from 'motion/react';
import type { ComponentProps } from 'react';
import { routeMotionVariants } from '../lib/motion';
import { StageRunMain } from './StageRunMain';

type Props = ComponentProps<typeof StageRunMain> & {
  focusMode: boolean;
};

export function StageRunMainArea({ focusMode, stage, ...mainProps }: Props) {
  const decisionCapable = !['info_recommend', 'export_artifact'].includes(stage.type)
    && (mainProps.workflow.quality_mode === 'deep' || (mainProps.workflow.quality_mode === 'balanced' && stage.variant_policy.enabled));
  return (
    <AnimatePresence initial={false} mode="popLayout">
      <motion.section
        animate="animate"
        className={`stage-run-main ${stage.type === 'info_recommend' ? 'info-main' : ''} ${stage.type === 'summary' ? 'summary-main' : ''} ${stage.type === 'outline' ? 'outline-main' : ''} ${stage.type === 'detail_outline' ? 'detail-main' : ''} ${stage.type === 'chapter_text' ? 'text-main' : ''} ${stage.type === 'cover_image' ? 'cover-main' : ''} ${stage.type === 'export_artifact' ? 'export-main' : ''} ${focusMode ? 'variant-focus-main' : ''} ${decisionCapable ? 'decision-capable' : ''}`}
        exit="exit"
        initial="initial"
        key={stage.id}
        variants={routeMotionVariants}
      >
        <StageRunMain {...mainProps} stage={stage} />
      </motion.section>
    </AnimatePresence>
  );
}
