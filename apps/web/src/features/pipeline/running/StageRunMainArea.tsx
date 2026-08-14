import { AnimatePresence, motion } from 'motion/react';
import type { ComponentProps } from 'react';
import { routeMotionVariants } from '../lib/motion';
import { StageRunMain } from './StageRunMain';

type Props = ComponentProps<typeof StageRunMain>;

export function StageRunMainArea({ stage, ...mainProps }: Props) {
  const decisionCapable = stage.type !== 'brief'
    && mainProps.workflow.quality_mode !== 'fast';
  return (
    <AnimatePresence initial={false} mode="popLayout">
      <motion.section
        animate="animate"
        className={`stage-run-main stage-${stage.type} ${stage.type === 'brief' ? 'brief-main' : ''} ${stage.type === 'spine' ? 'spine-main' : ''} ${stage.type === 'volumes' ? 'volumes-main' : ''} ${stage.type === 'detail' ? 'detail-main' : ''} ${stage.type === 'text' ? 'text-main' : ''} ${stage.type === 'cover' ? 'cover-main' : ''} ${stage.type === 'export' ? 'export-main' : ''} ${decisionCapable ? 'decision-capable' : ''}`}
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
