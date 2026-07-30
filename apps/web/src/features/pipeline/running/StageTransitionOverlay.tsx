import { AnimatePresence, motion } from 'motion/react';
import { Activity } from 'lucide-react';
import { useEffect, useMemo, useState } from 'react';
import type { RunEvent, WorkflowStage } from '../contracts';
import { routeMotionVariants } from '../lib/motion';

type Props = {
  events: RunEvent[];
  stage: WorkflowStage;
};

export function StageTransitionOverlay({ events, stage }: Props) {
  const latest = events.find((event) => event.type === 'node_started' && event.node_id === stage.id);
  const eventKey = useMemo(() => latest ? `${latest.type}-${latest.node_id}-${latest.elapsed_ms ?? latest.message ?? latest.label ?? ''}` : '', [latest]);
  const [visibleKey, setVisibleKey] = useState('');
  const visible = Boolean(eventKey && visibleKey === eventKey);

  useEffect(() => {
    if (!eventKey) return;
    setVisibleKey(eventKey);
    const timer = window.setTimeout(() => setVisibleKey(''), 1800);
    return () => window.clearTimeout(timer);
  }, [eventKey, latest?.type]);

  return (
    <AnimatePresence>
      {visible ? (
        <motion.div
          animate="animate"
          className="stage-transition-overlay"
          exit="exit"
          initial="initial"
          key={`${stage.id}-${latest?.type}-${events.length}`}
          variants={routeMotionVariants}
        >
          <section className="stage-transition-card">
            <p className="eyebrow">阶段启动</p>
            <h2><Activity size={20} />{stage.label}</h2>
            <p>正在读取上游产物、Wiki 约束和质量策略，准备进入当前阶段。</p>
          </section>
        </motion.div>
      ) : null}
    </AnimatePresence>
  );
}
