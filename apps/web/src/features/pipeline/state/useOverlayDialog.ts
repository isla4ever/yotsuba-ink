import { useEffect, useRef } from 'react';

type Options = {
  exitDurationMs?: number;
  initialFocusSelector?: string;
  onClose: () => void;
  open: boolean;
  suspended?: boolean;
};

type OverlayEntry = {
  dialog: HTMLElement;
  id: symbol;
  previouslyFocused: HTMLElement | null;
};

type BackgroundState = {
  ariaHidden: string | null;
  inert: boolean;
};

const focusableSelector = [
  'a[href]',
  'button:not([disabled])',
  'input:not([disabled]):not([type="hidden"])',
  'select:not([disabled])',
  'textarea:not([disabled])',
  '[tabindex]:not([tabindex="-1"])',
].join(',');

let bodyLockCount = 0;
let bodyOverflowBeforeLock = '';
const overlayStack: OverlayEntry[] = [];
const backgroundStates = new Map<HTMLElement, BackgroundState>();

export function hasOpenOverlay(): boolean {
  return overlayStack.length > 0;
}

export function useOverlayDialog<T extends HTMLElement>({
  exitDurationMs = 0,
  initialFocusSelector,
  onClose,
  open,
  suspended = false,
}: Options) {
  const dialogRef = useRef<T>(null);
  const onCloseRef = useRef(onClose);
  const suspendedRef = useRef(suspended);

  useEffect(() => {
    onCloseRef.current = onClose;
  }, [onClose]);

  useEffect(() => {
    suspendedRef.current = suspended;
  }, [suspended]);

  useEffect(() => {
    if (!open) return;
    const dialog = dialogRef.current;
    if (!dialog) return;

    const previouslyFocused = document.activeElement instanceof HTMLElement ? document.activeElement : null;
    const entry = { dialog, id: Symbol('overlay'), previouslyFocused };
    overlayStack.push(entry);
    lockBodyScroll();
    syncBackgroundInert();
    const focusInitial = () => {
      const initialFocus = initialFocusSelector
        ? dialog.querySelector<HTMLElement>(initialFocusSelector)
        : null;
      (initialFocus ?? dialog).focus();
    };
    const focusFrame = window.requestAnimationFrame(focusInitial);

    const handleFocusIn = (event: FocusEvent) => {
      if (suspendedRef.current || overlayStack[overlayStack.length - 1]?.id !== entry.id) return;
      const target = event.target;
      if (!(target instanceof Node) || !dialog.contains(target)) focusInitial();
    };

    const handleKeyDown = (event: KeyboardEvent) => {
      if (suspendedRef.current) return;
      if (event.key === 'Escape') {
        event.preventDefault();
        event.stopPropagation();
        onCloseRef.current();
        return;
      }
      if (event.key !== 'Tab') return;

      const focusable = Array.from(dialog.querySelectorAll<HTMLElement>(focusableSelector)).filter(isVisible);
      if (!focusable.length) {
        event.preventDefault();
        dialog.focus();
        return;
      }

      const first = focusable[0];
      const last = focusable[focusable.length - 1];
      const active = document.activeElement;
      if (event.shiftKey && (active === first || active === dialog)) {
        event.preventDefault();
        last.focus();
      } else if (!event.shiftKey && active === last) {
        event.preventDefault();
        first.focus();
      }
    };

    document.addEventListener('focusin', handleFocusIn, true);
    document.addEventListener('keydown', handleKeyDown, true);
    return () => {
      window.cancelAnimationFrame(focusFrame);
      document.removeEventListener('focusin', handleFocusIn, true);
      document.removeEventListener('keydown', handleKeyDown, true);
      const release = () => releaseOverlay(entry);
      const reducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
      if (exitDurationMs > 0 && !reducedMotion) window.setTimeout(release, exitDurationMs);
      else release();
    };
  }, [exitDurationMs, initialFocusSelector, open]);

  return dialogRef;
}

function releaseOverlay(entry: OverlayEntry) {
  const index = overlayStack.findIndex((item) => item.id === entry.id);
  if (index < 0) return;
  const wasTop = index === overlayStack.length - 1;
  const topEntry = overlayStack[overlayStack.length - 1];
  // Preserve the original opener when a parent and nested confirmation unmount together.
  if (
    !wasTop
    && topEntry
    && (
      !topEntry.previouslyFocused
      || entry.dialog.contains(topEntry.previouslyFocused)
      || topEntry.dialog.contains(topEntry.previouslyFocused)
    )
  ) {
    topEntry.previouslyFocused = entry.previouslyFocused;
  }
  overlayStack.splice(index, 1);
  unlockBodyScroll();
  syncBackgroundInert();
  if (wasTop && entry.previouslyFocused?.isConnected) entry.previouslyFocused.focus();
}

function syncBackgroundInert() {
  // The exempt root must be the <body>-level ancestor that CONTAINS the top
  // dialog. Portaled dialogs resolve to their portal container; dialogs
  // rendered inline inside #root resolve to #root itself (the focus trap and
  // backdrop still isolate them). Using dialog.parentElement here used to
  // inert the entire app whenever a dialog was not portaled to <body>.
  const topDialog = overlayStack[overlayStack.length - 1]?.dialog;
  const topOverlayRoot = topDialog ? bodyChildContaining(topDialog) : null;
  const bodyChildren = Array.from(document.body.children).filter(
    (element): element is HTMLElement => element instanceof HTMLElement && !['SCRIPT', 'STYLE'].includes(element.tagName),
  );

  for (const element of bodyChildren) {
    if (element === topOverlayRoot) {
      restoreBackgroundState(element);
      continue;
    }
    if (!topOverlayRoot) {
      restoreBackgroundState(element);
      continue;
    }
    if (!backgroundStates.has(element)) {
      backgroundStates.set(element, {
        ariaHidden: element.getAttribute('aria-hidden'),
        inert: element.inert,
      });
    }
    element.inert = true;
    element.setAttribute('aria-hidden', 'true');
  }

  for (const element of Array.from(backgroundStates.keys())) {
    if (!element.isConnected || !bodyChildren.includes(element)) backgroundStates.delete(element);
  }
}

function bodyChildContaining(node: HTMLElement): HTMLElement | null {
  let current: HTMLElement | null = node;
  while (current && current.parentElement !== document.body) current = current.parentElement;
  return current;
}

function restoreBackgroundState(element: HTMLElement) {
  const state = backgroundStates.get(element);
  if (!state) return;
  element.inert = state.inert;
  if (state.ariaHidden === null) element.removeAttribute('aria-hidden');
  else element.setAttribute('aria-hidden', state.ariaHidden);
  backgroundStates.delete(element);
}

function isVisible(element: HTMLElement) {
  const style = window.getComputedStyle(element);
  return style.display !== 'none' && style.visibility !== 'hidden' && element.getClientRects().length > 0;
}

function lockBodyScroll() {
  if (bodyLockCount === 0) {
    bodyOverflowBeforeLock = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
  }
  bodyLockCount += 1;
}

function unlockBodyScroll() {
  bodyLockCount = Math.max(0, bodyLockCount - 1);
  if (bodyLockCount === 0) document.body.style.overflow = bodyOverflowBeforeLock;
}
