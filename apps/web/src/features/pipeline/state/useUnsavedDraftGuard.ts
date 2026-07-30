import { useCallback, useEffect, useRef, useState } from 'react';
import { useBlocker } from 'react-router-dom';

export type UnsavedDraftIntent = {
  destinationLabel?: string;
  kind: 'close' | 'navigate' | 'switch';
  scopeLabel?: string;
};

type GuardOptions = {
  dirty: boolean;
  readOnly?: boolean;
  scopeLabel?: string;
};

type DraftEditingFocus = {
  ariaLabel: string;
  detailField: string;
  element: HTMLElement;
  id: string;
  name: string;
};

export function useUnsavedDraftGuard({ dirty, readOnly = false, scopeLabel }: GuardOptions) {
  const [intent, setIntent] = useState<UnsavedDraftIntent | null>(null);
  const pendingActionRef = useRef<null | (() => void)>(null);
  const editingFocusRef = useRef<DraftEditingFocus | null>(null);
  const dismissedNavigationRef = useRef(false);
  const guarded = shouldConfirmUnsavedDraft(dirty, readOnly);
  const blocker = useBlocker(guarded);

  const requestAction = useCallback((nextIntent: UnsavedDraftIntent, action: () => void) => {
    if (!guarded) {
      action();
      return;
    }
    pendingActionRef.current = action;
    setIntent(nextIntent);
  }, [guarded]);

  const cancelDiscard = useCallback(() => {
    pendingActionRef.current = null;
    setIntent(null);
    if (blocker.state === 'blocked') {
      dismissedNavigationRef.current = true;
      blocker.reset();
    }
    const editingFocus = editingFocusRef.current;
    window.setTimeout(() => {
      window.requestAnimationFrame(() => {
        resolveDraftEditingFocus(editingFocus)?.focus();
        window.requestAnimationFrame(() => resolveDraftEditingFocus(editingFocus)?.focus());
      });
    }, 0);
  }, [blocker]);

  const confirmDiscard = useCallback(() => {
    const action = pendingActionRef.current;
    pendingActionRef.current = null;
    setIntent(null);
    action?.();
  }, []);

  useEffect(() => {
    const rememberEditingFocus = (event: FocusEvent) => {
      const target = event.target;
      if (target instanceof HTMLElement && isDraftEditingControl(target)) editingFocusRef.current = draftEditingFocus(target);
    };
    if (document.activeElement instanceof HTMLElement && isDraftEditingControl(document.activeElement)) {
      editingFocusRef.current = draftEditingFocus(document.activeElement);
    }
    document.addEventListener('focusin', rememberEditingFocus);
    return () => document.removeEventListener('focusin', rememberEditingFocus);
  }, []);

  useEffect(() => {
    if (!guarded) return;
    const handleBeforeUnload = (event: BeforeUnloadEvent) => {
      event.preventDefault();
      event.returnValue = '';
    };
    window.addEventListener('beforeunload', handleBeforeUnload);
    return () => window.removeEventListener('beforeunload', handleBeforeUnload);
  }, [guarded]);

  useEffect(() => {
    if (blocker.state === 'unblocked') {
      dismissedNavigationRef.current = false;
      return;
    }
    if (blocker.state !== 'blocked') return;
    if (!shouldPromptBlockedNavigation(blocker.state, Boolean(intent), dismissedNavigationRef.current)) return;
    pendingActionRef.current = blocker.proceed;
    setIntent({ kind: 'navigate', scopeLabel });
  }, [blocker, blocker.state, intent, scopeLabel]);

  return { cancelDiscard, confirmDiscard, intent, requestAction };
}

export function shouldConfirmUnsavedDraft(dirty: boolean, readOnly = false) {
  return dirty && !readOnly;
}

export function draftsEqual(left: unknown, right: unknown) {
  return JSON.stringify(left) === JSON.stringify(right);
}

export function shouldPromptBlockedNavigation(blockerState: string, hasIntent: boolean, navigationDismissed: boolean) {
  return blockerState === 'blocked' && !hasIntent && !navigationDismissed;
}

function isDraftEditingControl(element: HTMLElement) {
  return element.matches('input:not([type="hidden"]), select, textarea, [contenteditable="true"]')
    && !element.closest('[role="alertdialog"]');
}

function draftEditingFocus(element: HTMLElement): DraftEditingFocus {
  return {
    ariaLabel: element.getAttribute('aria-label') ?? '',
    detailField: element.dataset.detailField ?? '',
    element,
    id: element.id,
    name: element.getAttribute('name') ?? '',
  };
}

function resolveDraftEditingFocus(snapshot: DraftEditingFocus | null) {
  if (!snapshot) return null;
  if (snapshot.element.isConnected) return snapshot.element;
  const controls = Array.from(document.querySelectorAll<HTMLElement>(
    'input:not([type="hidden"]), select, textarea, [contenteditable="true"]',
  ));
  return controls.find((element) => (
    (snapshot.detailField && element.dataset.detailField === snapshot.detailField)
    || (snapshot.id && element.id === snapshot.id)
    || (snapshot.name && element.getAttribute('name') === snapshot.name)
    || (snapshot.ariaLabel && element.getAttribute('aria-label') === snapshot.ariaLabel)
  )) ?? null;
}
