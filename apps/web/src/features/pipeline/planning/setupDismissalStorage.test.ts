import { afterEach, describe, expect, it, vi } from 'vitest';
import { loadSetupDismissed, saveSetupDismissed, setupDismissalKey } from './setupDismissalStorage';

function memoryWindow() {
  const store = new Map<string, string>();
  return {
    localStorage: {
      getItem: (key: string) => store.get(key) ?? null,
      setItem: (key: string, value: string) => void store.set(key, value),
      removeItem: (key: string) => void store.delete(key),
    },
    __store: store,
  };
}

describe('setup dismissal persistence (Phase 12 A11)', () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it('persists 稍后继续 per workflow id and clears it on return', () => {
    const win = memoryWindow();
    vi.stubGlobal('window', win);

    expect(loadSetupDismissed('wf-a')).toBe(false);
    saveSetupDismissed('wf-a', true);
    expect(win.__store.get(setupDismissalKey('wf-a'))).toBe('1');
    expect(loadSetupDismissed('wf-a')).toBe(true);
    // Other workflows keep their own flag.
    expect(loadSetupDismissed('wf-b')).toBe(false);

    saveSetupDismissed('wf-a', false);
    expect(win.__store.has(setupDismissalKey('wf-a'))).toBe(false);
    expect(loadSetupDismissed('wf-a')).toBe(false);
  });

  it('treats unavailable or corrupted storage as not dismissed', () => {
    vi.stubGlobal('window', {
      localStorage: {
        getItem: () => { throw new Error('denied'); },
        setItem: () => { throw new Error('denied'); },
        removeItem: () => { throw new Error('denied'); },
      },
    });
    expect(loadSetupDismissed('wf-a')).toBe(false);
    expect(() => saveSetupDismissed('wf-a', true)).not.toThrow();

    const win = memoryWindow();
    vi.stubGlobal('window', win);
    win.__store.set(setupDismissalKey('wf-a'), 'garbage');
    expect(loadSetupDismissed('wf-a')).toBe(false);
  });
});
