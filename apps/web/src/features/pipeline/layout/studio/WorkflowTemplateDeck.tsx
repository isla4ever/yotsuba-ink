import { ArrowRight, Check, CircleAlert } from 'lucide-react';
import { gsap } from 'gsap';
import { useGSAP } from '@gsap/react';
import { useMemo, useRef, type CSSProperties, type KeyboardEvent } from 'react';
import type { QualityMode, WorkflowStage } from '../../contracts';
import { stageArtifactLabel, stageConfigurationReadiness } from '../../lib/planningReadiness';
import {
  workflowTemplateDeckLayer,
  workflowTemplateDeckPose,
  workflowTemplateDeckPoseVars,
} from '../../lib/workflowTemplateDeckLayout';

gsap.registerPlugin(useGSAP);

type Props = {
  activeStageId: string;
  qualityMode: QualityMode;
  stages: WorkflowStage[];
  onSelect: (stageId: string) => void;
};

export function WorkflowTemplateDeck({ activeStageId, qualityMode, stages, onSelect }: Props) {
  const deckRef = useRef<HTMLElement | null>(null);
  const buttonsRef = useRef<Array<HTMLButtonElement | null>>([]);
  const selectedIndexRef = useRef(0);
  const itemCountRef = useRef(0);
  const lastSelectedIndexRef = useRef<number | null>(null);
  const scrollFrameRef = useRef<number | null>(null);
  const timelineRef = useRef<ReturnType<typeof gsap.timeline> | null>(null);
  const items = useMemo(() => stages.map((stage, index) => {
    const readiness = stageConfigurationReadiness(stage);
    return {
      artifact: stageArtifactLabel(stage),
      id: stage.id,
      label: stage.label,
      model: stage.type === 'export' ? '系统确定性执行' : stage.model_settings.model || '未指定模型',
      nextStage: stages[index + 1]?.label ?? '流程完成',
      ready: readiness.ready,
      statusLabel: readiness.ready ? '配置就绪' : `待补 ${readiness.missingLabels.length} 项`,
    };
  }), [stages]);
  const selectedIndex = Math.max(0, items.findIndex((item) => item.id === activeStageId));
  const selected = items[selectedIndex] ?? items[0];
  selectedIndexRef.current = selectedIndex;
  itemCountRef.current = items.length;

  useGSAP((_, contextSafe) => {
    const root = deckRef.current;
    const viewport = root?.querySelector<HTMLElement>('.artifact-deck-viewport');
    const slots = root ? Array.from(root.querySelectorAll<HTMLElement>('.artifact-sheet-slot')) : [];
    if (!root || !viewport || !slots.length) return;

    const setCurrentPoses = () => {
      timelineRef.current?.kill();
      slots.forEach((slot, index) => {
        const pose = workflowTemplateDeckPose(index, viewport.clientWidth, itemCountRef.current);
        gsap.set(slot, workflowTemplateDeckPoseVars(pose));
      });
      if (viewport.clientWidth <= 560) {
        if (scrollFrameRef.current !== null) window.cancelAnimationFrame(scrollFrameRef.current);
        scrollFrameRef.current = window.requestAnimationFrame(() => {
          buttonsRef.current[selectedIndexRef.current]?.scrollIntoView({
            behavior: 'auto',
            block: 'nearest',
            inline: 'center',
          });
        });
      }
    };
    const handleResize = contextSafe?.(setCurrentPoses) ?? setCurrentPoses;
    handleResize();
    root.dataset.motionReady = 'true';
    lastSelectedIndexRef.current = selectedIndexRef.current;

    if (typeof ResizeObserver === 'undefined') return;
    const resizeObserver = new ResizeObserver(handleResize);
    resizeObserver.observe(viewport);
    return () => {
      resizeObserver.disconnect();
      timelineRef.current?.kill();
      if (scrollFrameRef.current !== null) window.cancelAnimationFrame(scrollFrameRef.current);
    };
  }, { scope: deckRef });

  useGSAP(() => {
    const root = deckRef.current;
    const viewport = root?.querySelector<HTMLElement>('.artifact-deck-viewport');
    if (!root || !viewport) return;

    const reduceMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    const changed = lastSelectedIndexRef.current !== null && lastSelectedIndexRef.current !== selectedIndex;
    timelineRef.current?.kill();
    gsap.set(root.querySelectorAll('.artifact-sheet-highlight'), { autoAlpha: 0 });

    const highlight = root.querySelector<HTMLElement>('.artifact-sheet-slot.is-selected .artifact-sheet-highlight');
    if (changed && !reduceMotion && highlight) {
      const timeline = gsap.timeline({ defaults: { overwrite: 'auto' } });
      gsap.set(highlight, { autoAlpha: 0, xPercent: -118 });
      timeline.to(highlight, {
        autoAlpha: 0.34,
        duration: 0.22,
        ease: 'power2.inOut',
        xPercent: 112,
      }).set(highlight, { autoAlpha: 0 });
      timelineRef.current = timeline;
    }
    lastSelectedIndexRef.current = selectedIndex;

    if (scrollFrameRef.current !== null) window.cancelAnimationFrame(scrollFrameRef.current);
    if (viewport.clientWidth <= 560) {
      scrollFrameRef.current = window.requestAnimationFrame(() => {
        buttonsRef.current[selectedIndex]?.scrollIntoView({
          behavior: reduceMotion ? 'auto' : 'smooth',
          block: 'nearest',
          inline: 'center',
        });
      });
    }
  }, { dependencies: [items.length, selectedIndex], scope: deckRef });

  const handleKeyDown = (event: KeyboardEvent<HTMLButtonElement>, index: number) => {
    if (!['ArrowLeft', 'ArrowRight', 'Home', 'End'].includes(event.key)) return;
    event.preventDefault();
    const next = event.key === 'Home'
      ? 0
      : event.key === 'End'
        ? items.length - 1
        : (index + (event.key === 'ArrowRight' ? 1 : items.length - 1)) % items.length;
    const item = items[next];
    if (!item) return;
    onSelect(item.id);
    buttonsRef.current[next]?.focus();
  };

  return (
    <section aria-labelledby="workflow-deck-title" className="workflow-template-stage-shell">
      <header className="workflow-template-stage-head">
        <div>
          <p className="eyebrow">创作流程</p>
          <h2 id="workflow-deck-title">八阶段稿件栈</h2>
        </div>
        <div className="workflow-template-stage-position">
          <strong>第 {selectedIndex + 1}/{items.length} 阶段</strong>
          <span>选择稿件查看右侧配置</span>
        </div>
      </header>
      <nav
        aria-label="工作流阶段配置"
        className="artifact-deck-surface workflow-template-artifact-deck"
        data-mode={qualityMode}
        ref={deckRef}
        style={{
          '--deck-marker-position': `${15.5 + (items.length > 1 ? selectedIndex / (items.length - 1) : 0.5) * 69}%`,
        } as CSSProperties}
      >
        <div className="artifact-deck-viewport">
          <span aria-hidden="true" className="artifact-deck-horizon" />
          <ol aria-label="八阶段稿件栈" className="artifact-deck">
            {items.map((item, index) => {
              const active = item.id === activeStageId;
              const Icon = item.ready ? Check : CircleAlert;
              return (
                <li
                  className={`artifact-sheet-slot ${item.ready ? 'is-confirmed' : 'is-attention'}${active ? ' is-selected' : ''}`}
                  key={item.id}
                  style={{ zIndex: workflowTemplateDeckLayer(index, items.length) }}
                >
                  <button
                    aria-current={active ? 'step' : undefined}
                    aria-label={`第 ${index + 1} 阶段，${item.label}，${item.statusLabel}`}
                    className="artifact-sheet-hit"
                    onClick={() => onSelect(item.id)}
                    onKeyDown={(event) => handleKeyDown(event, index)}
                    ref={(node) => { buttonsRef.current[index] = node; }}
                    tabIndex={active ? 0 : -1}
                    type="button"
                  />
                  <div aria-hidden="true" className="artifact-sheet-body">
                    <span className="artifact-sheet-depth" />
                    <span className="artifact-sheet-stack"><i /><i /><i /></span>
                    <div className="artifact-sheet">
                      <span className="artifact-sheet-highlight" />
                      <span className="artifact-sheet-index">{String(index + 1).padStart(2, '0')}</span>
                      <span className="artifact-sheet-icon"><Icon size={15} /></span>
                      <span className="artifact-sheet-copy">
                        <strong>{item.label}</strong>
                        <small>{item.artifact}</small>
                        <span className="artifact-sheet-folio"><i /><i /><i /><i /></span>
                      </span>
                      <span className="artifact-sheet-state">{item.statusLabel}</span>
                    </div>
                  </div>
                </li>
              );
            })}
          </ol>
          <div aria-hidden="true" className="artifact-deck-pedestal"><span /><i /></div>
        </div>
        {selected ? (
          <footer className="artifact-deck-caption">
            <div className="artifact-deck-artifact">
              <p><span className={`artifact-status-dot ${selected.ready ? 'is-confirmed' : 'is-attention'}`} />当前阶段</p>
              <h3>{selected.label}</h3>
              <span>{selected.artifact}</span>
            </div>
            <div className="artifact-deck-decision">
              <small>配置状态</small>
              <strong>{selected.statusLabel}</strong>
            </div>
            <div className="artifact-deck-writeback">
              <small>执行模型</small>
              <strong>{selected.model}</strong>
            </div>
            <div className="artifact-deck-next">
              <small>下一阶段</small>
              <strong><span>{selected.nextStage}</span><ArrowRight size={14} /></strong>
              <span>当前阶段定稿后进入</span>
            </div>
          </footer>
        ) : null}
      </nav>
    </section>
  );
}
