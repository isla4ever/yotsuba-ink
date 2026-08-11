import { ArrowRight, Check, CircleAlert, FileStack, Settings2 } from 'lucide-react';
import { gsap } from 'gsap';
import { useGSAP } from '@gsap/react';
import { useMemo, useRef, type CSSProperties, type KeyboardEvent } from 'react';
import type { InspectorTarget, RunEvent, WorkflowDefinition } from '../contracts';
import { buildArtifactDeckItems } from './artifactDeckModel';
import { artifactDeckLayer, artifactDeckPose } from './artifactDeckLayout';
import { artifactDeckPoseVars } from './artifactDeckMotion';

gsap.registerPlugin(useGSAP);

type Props = {
  events: RunEvent[];
  onOpenConfig?: () => void;
  onOpenStage?: (stageId: string) => void;
  onSelect: (target: InspectorTarget) => void;
  selectedId: string;
  workflow: WorkflowDefinition;
};

export function ArtifactDeck({ events, onOpenConfig, onOpenStage, onSelect, selectedId, workflow }: Props) {
  const deckRef = useRef<HTMLElement | null>(null);
  const buttonsRef = useRef<Array<HTMLButtonElement | null>>([]);
  const itemCountRef = useRef(0);
  const lastSelectedIndexRef = useRef<number | null>(null);
  const scrollFrameRef = useRef<number | null>(null);
  const selectedIndexRef = useRef(0);
  const timelineRef = useRef<ReturnType<typeof gsap.timeline> | null>(null);
  const items = useMemo(
    () => buildArtifactDeckItems(workflow, events, selectedId),
    [events, selectedId, workflow],
  );
  const selectedIndex = Math.max(0, items.findIndex((item) => item.id === selectedId));
  const selected = items[selectedIndex] ?? items[0];
  itemCountRef.current = items.length;
  selectedIndexRef.current = selectedIndex;

  useGSAP((_, contextSafe) => {
    const root = deckRef.current;
    const viewport = root?.querySelector<HTMLElement>('.artifact-deck-viewport');
    const slots = root ? Array.from(root.querySelectorAll<HTMLElement>('.artifact-sheet-slot')) : [];
    if (!root || !viewport || !slots.length) return;

    const setCurrentPoses = () => {
      timelineRef.current?.kill();
      slots.forEach((slot, index) => {
        const pose = artifactDeckPose(index, selectedIndexRef.current, viewport.clientWidth, itemCountRef.current);
        gsap.set(slot, artifactDeckPoseVars(pose));
      });
      if (viewport.clientWidth <= 760) {
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
    const highlights = root.querySelectorAll('.artifact-sheet-highlight');
    gsap.set(highlights, { autoAlpha: 0 });

    const activeSheet = root.querySelector<HTMLElement>('.artifact-sheet-slot.is-selected .artifact-sheet-highlight');
    if (changed && !reduceMotion && activeSheet) {
      const timeline = gsap.timeline({ defaults: { overwrite: 'auto' } });
      gsap.set(activeSheet, { autoAlpha: 0, xPercent: -118 });
      timeline.to(activeSheet, {
        autoAlpha: 0.34,
        duration: 0.22,
        ease: 'power2.inOut',
        xPercent: 112,
      }).set(activeSheet, { autoAlpha: 0 });
      timelineRef.current = timeline;
    }
    lastSelectedIndexRef.current = selectedIndex;

    if (scrollFrameRef.current !== null) window.cancelAnimationFrame(scrollFrameRef.current);
    if (viewport.clientWidth <= 760) {
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
    onSelect({ kind: 'stage', id: item.id });
    buttonsRef.current[next]?.focus();
  };

  const handleSheetClick = (id: string) => {
    onSelect({ kind: 'stage', id });
  };

  return (
    <section
      className="artifact-deck-surface"
      data-mode={workflow.quality_mode}
      ref={deckRef}
      style={{
        '--deck-marker-position': `${15.5 + (items.length > 1 ? selectedIndex / (items.length - 1) : 0.5) * 69}%`,
      } as CSSProperties}
    >
      <div className="artifact-deck-viewport">
        <span aria-hidden="true" className="artifact-deck-horizon" />
        <ol aria-label="八阶段稿件栈" className="artifact-deck">
          {items.map((item, index) => {
            const active = item.id === selectedId;
            const position = index < selectedIndex ? 'before' : index > selectedIndex ? 'after' : 'active-position';
            const Icon = item.status === 'confirmed' ? Check : ['attention', 'awaiting'].includes(item.status) ? CircleAlert : FileStack;
            return (
              <li
                className={`artifact-sheet-slot is-${item.status} is-${position}${active ? ' is-selected' : ''}`}
                key={item.id}
                style={{
                  '--deck-index': index,
                  '--deck-relative': index - selectedIndex,
                  zIndex: artifactDeckLayer(index, items.length),
                } as CSSProperties}
              >
                <button
                  aria-current={active ? 'step' : undefined}
                  aria-label={`第 ${index + 1} 阶段，${item.label}，${item.statusLabel}${onOpenStage ? '；双击打开阶段' : ''}`}
                  className="artifact-sheet-hit"
                  onClick={() => handleSheetClick(item.id)}
                  onDoubleClick={onOpenStage ? () => onOpenStage(item.id) : undefined}
                  onKeyDown={(event) => handleKeyDown(event, index)}
                  ref={(node) => { buttonsRef.current[index] = node; }}
                  tabIndex={active ? 0 : -1}
                  type="button"
                />
                <div aria-hidden="true" className="artifact-sheet-body">
                  <span aria-hidden="true" className="artifact-sheet-depth" />
                  <span aria-hidden="true" className="artifact-sheet-stack"><i /><i /><i /></span>
                  <div className="artifact-sheet">
                    <span aria-hidden="true" className="artifact-sheet-highlight" />
                    <span className="artifact-sheet-index">{String(index + 1).padStart(2, '0')}</span>
                    <span className="artifact-sheet-icon"><Icon size={15} /></span>
                    <span className="artifact-sheet-copy">
                      <strong>{item.label}</strong>
                      <small>{item.artifact}</small>
                      <span aria-hidden="true" className="artifact-sheet-folio">
                        <i /><i /><i /><i />
                      </span>
                    </span>
                    <span className="artifact-sheet-state">{item.statusLabel}</span>
                  </div>
                </div>
              </li>
            );
          })}
        </ol>
        <div aria-hidden="true" className="artifact-deck-pedestal">
          <span /><i />
        </div>
        <div aria-label="细纲定稿后的并行阶段拓扑" className="artifact-deck-branchmap">
          <span>细纲定稿</span><i aria-hidden="true" />
          <div><b>正文主线</b><b>封面 · 预览并行</b></div>
        </div>
      </div>
      {selected ? (
        <footer className="artifact-deck-caption">
          <div className="artifact-deck-artifact">
            <p><span className={`artifact-status-dot is-${selected.status}`} />当前产物</p>
            <h3>{selected.label}</h3>
            <span>{selected.artifact}</span>
          </div>
          <div className="artifact-deck-decision">
            <small>当前决策</small>
            <strong>{selected.decision}</strong>
          </div>
          <div className="artifact-deck-writeback">
            <small>定稿后写回</small>
            <strong>{selected.writeback}</strong>
          </div>
          <div className="artifact-deck-next">
            <small>下一阶段需要</small>
            <strong><span>{selected.nextStage}</span><ArrowRight size={14} /></strong>
            <span>{selected.nextDependency}</span>
          </div>
          {onOpenConfig ? (
            <button aria-label={`编辑${selected.label}阶段配置`} className="artifact-deck-config" onClick={onOpenConfig} title="编辑当前阶段配置" type="button">
              <Settings2 size={16} />
            </button>
          ) : null}
        </footer>
      ) : null}
    </section>
  );
}
