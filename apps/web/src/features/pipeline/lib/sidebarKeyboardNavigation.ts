const navigationKeys = new Set(['ArrowDown', 'ArrowUp', 'Home', 'End']);

export function nextSidebarFocusTarget(root: HTMLElement | null, key: string, active: Element | null) {
  if (!root || !navigationKeys.has(key)) return null;
  const items = [...root.querySelectorAll<HTMLButtonElement>('button:not(:disabled)')];
  const currentIndex = items.indexOf(active as HTMLButtonElement);
  if (currentIndex < 0 || !items.length) return null;
  const nextIndex = key === 'Home'
    ? 0
    : key === 'End'
      ? items.length - 1
      : (currentIndex + (key === 'ArrowDown' ? 1 : items.length - 1)) % items.length;
  return items[nextIndex] ?? null;
}
