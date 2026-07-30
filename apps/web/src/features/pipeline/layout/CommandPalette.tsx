import { Search } from 'lucide-react';
import { AnimatePresence, motion } from 'motion/react';
import { memo, useEffect, useId, useRef, useState, type KeyboardEvent as ReactKeyboardEvent } from 'react';
import { createPortal } from 'react-dom';
import {
  bibleSectionFromCommandId,
  buildPaletteCommands,
  filterPaletteCommands,
  firstEnabledCommandId,
  groupPaletteCommands,
  isEditableEventTarget,
  isPaletteShortcut,
  movePaletteHighlight,
  paletteBibleCommandPrefix,
  paletteStageCommandPrefix,
  type PaletteCommand,
  type PaletteContext,
} from './commandPaletteModel';
import { backdropMotionVariants, dialogMotionVariants, overlayExitDurationMs } from '../lib/motion';
import { useRunStateContext, useUICommandContext, useWorkflowConfigContext } from '../state/pipelineShellContext';
import { hasOpenOverlay, useOverlayDialog } from '../state/useOverlayDialog';

function anotherOverlayIsOpen(): boolean {
  if (hasOpenOverlay()) return true;
  return Boolean(document.querySelector('[role="dialog"], [role="alertdialog"], .knowledge-blocker-backdrop'));
}

/** Memoized (Phase 12 F5): only low-frequency shell slices are consumed. */
export const CommandPalette = memo(function CommandPalette() {
  const run = useRunStateContext();
  const { qualityMode, routePolicy, workflow } = useWorkflowConfigContext();
  const actions = useUICommandContext();
  const open = actions.commandPaletteOpen;
  const onOpen = actions.openCommandPalette;
  const onClose = actions.closeCommandPalette;
  const context: PaletteContext = {
    policy: routePolicy,
    qualityMode,
    runHasStarted: run.runHasStarted,
    sidebarExpanded: actions.sidebarExpanded,
    stageRuntimes: run.stageRuntimes,
    stages: workflow.nodes,
    theme: actions.theme,
  };
  const baseId = useId();
  const listId = `${baseId}-list`;
  const inputRef = useRef<HTMLInputElement | null>(null);
  const onOpenRef = useRef(onOpen);
  const [query, setQuery] = useState('');
  const [highlightedId, setHighlightedId] = useState('');
  const dialogRef = useOverlayDialog<HTMLElement>({ exitDurationMs: overlayExitDurationMs.dialog, onClose, open });

  useEffect(() => {
    onOpenRef.current = onOpen;
  }, [onOpen]);

  useEffect(() => {
    const handleShortcut = (event: KeyboardEvent) => {
      if (!isPaletteShortcut(event)) return;
      if (isEditableEventTarget(event.target instanceof HTMLElement ? event.target : null)) return;
      if (open || anotherOverlayIsOpen()) return;
      event.preventDefault();
      onOpenRef.current();
    };
    window.addEventListener('keydown', handleShortcut);
    return () => window.removeEventListener('keydown', handleShortcut);
  }, [open]);

  useEffect(() => {
    if (!open) return;
    setQuery('');
    setHighlightedId('');
    // Double RAF runs after the overlay hook's own focus frame so the input keeps focus.
    const frame = window.requestAnimationFrame(() => window.requestAnimationFrame(() => inputRef.current?.focus()));
    return () => window.cancelAnimationFrame(frame);
  }, [open]);

  const filtered = filterPaletteCommands(buildPaletteCommands(context), query);
  const groups = groupPaletteCommands(filtered);
  const highlightId = filtered.some((item) => item.id === highlightedId && !item.disabled)
    ? highlightedId
    : firstEnabledCommandId(filtered);
  const optionDomId = (commandId: string) => `${baseId}-${commandId.replace(':', '-')}`;

  useEffect(() => {
    if (!open || !highlightId) return;
    document.getElementById(`${baseId}-${highlightId.replace(':', '-')}`)?.scrollIntoView({ block: 'nearest' });
  }, [baseId, highlightId, open]);

  const runCommand = (item: PaletteCommand) => {
    if (item.disabled) return;
    if (item.closesPalette) onClose();
    if (item.id.startsWith(paletteStageCommandPrefix)) {
      actions.navigateStage(item.id.slice(paletteStageCommandPrefix.length));
      return;
    }
    if (item.id.startsWith(paletteBibleCommandPrefix)) {
      const section = bibleSectionFromCommandId(item.id);
      if (section) actions.navigateBible(section);
      return;
    }
    if (item.id === 'nav:planning') actions.navigatePlanning();
    else if (item.id === 'nav:studio') actions.navigateStudio();
    else if (item.id === 'studio:new-project') actions.requestNewProject();
    else if (item.id === 'open:knowledge') actions.openKnowledge();
    else if (item.id === 'open:history') actions.openHistory();
    else if (item.id === 'open:settings') actions.openSettings();
    else if (item.id === 'appearance:theme') actions.toggleTheme();
    else if (item.id === 'appearance:sidebar') actions.toggleSidebar();
  };

  const handleInputKeyDown = (event: ReactKeyboardEvent<HTMLInputElement>) => {
    if (event.key === 'ArrowDown' || event.key === 'ArrowUp') {
      event.preventDefault();
      const next = movePaletteHighlight(filtered, highlightId, event.key === 'ArrowDown' ? 1 : -1);
      if (next) setHighlightedId(next);
      return;
    }
    if (event.key === 'Enter') {
      event.preventDefault();
      const item = filtered.find((candidate) => candidate.id === highlightId);
      if (item) runCommand(item);
    }
  };

  const content = (
    <AnimatePresence>
      {open ? (
        <motion.div
          animate="animate"
          className="app-overlay-backdrop command-palette-backdrop"
          exit="exit"
          initial="initial"
          onClick={(event) => {
            if (event.currentTarget === event.target) onClose();
          }}
          role="presentation"
          variants={backdropMotionVariants}
        >
          <motion.section
            animate="animate"
            aria-label="全局命令面板"
            aria-modal="true"
            className="app-dialog-surface command-palette"
            exit="exit"
            initial="initial"
            onClick={(event) => event.stopPropagation()}
            ref={dialogRef}
            role="dialog"
            tabIndex={-1}
            variants={dialogMotionVariants}
          >
            <div className="command-palette-input-row">
              <span aria-hidden="true" className="command-palette-input-icon"><Search size={14} /></span>
              <input
                aria-activedescendant={highlightId ? optionDomId(highlightId) : undefined}
                aria-autocomplete="list"
                aria-controls={listId}
                aria-expanded="true"
                className="command-palette-input"
                onChange={(event) => setQuery(event.target.value)}
                onKeyDown={handleInputKeyDown}
                placeholder="搜索命令，如：正文 / 设置 / 主题"
                ref={inputRef}
                role="combobox"
                type="text"
                value={query}
              />
              <kbd aria-hidden="true" className="command-palette-kbd">Esc</kbd>
            </div>
            <div aria-label="命令列表" className="command-palette-list" id={listId} role="listbox">
              {groups.length === 0 ? (
                <p className="command-palette-empty">没有匹配「{query.trim()}」的命令</p>
              ) : (
                groups.map((group) => (
                  <div aria-label={group.label} className="command-palette-group" key={group.id} role="group">
                    <p aria-hidden="true" className="command-palette-group-label">{group.label}</p>
                    {group.commands.map((item) => (
                      <div
                        aria-disabled={item.disabled || undefined}
                        aria-selected={item.id === highlightId}
                        className={`command-palette-option${item.disabled ? ' disabled' : ''}`}
                        id={optionDomId(item.id)}
                        key={item.id}
                        onClick={() => runCommand(item)}
                        onMouseEnter={() => {
                          if (!item.disabled) setHighlightedId(item.id);
                        }}
                        role="option"
                      >
                        <span className="command-palette-option-title">{item.title}</span>
                        <span className="command-palette-option-detail">{item.disabled ? item.disabledReason : item.detail}</span>
                      </div>
                    ))}
                  </div>
                ))
              )}
            </div>
          </motion.section>
        </motion.div>
      ) : null}
    </AnimatePresence>
  );

  if (typeof document === 'undefined') return content;
  return createPortal(content, document.body);
});
