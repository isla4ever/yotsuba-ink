export type WritingViewMode = 'writing' | 'review' | 'focus';

export type WritingViewState = {
  current: WritingViewMode;
  restore: Exclude<WritingViewMode, 'focus'>;
};

export const initialWritingViewState: WritingViewState = {
  current: 'writing',
  restore: 'writing',
};

export function selectWritingViewMode(
  state: WritingViewState,
  next: WritingViewMode,
): WritingViewState {
  if (next === 'focus') {
    return {
      current: 'focus',
      restore: state.current === 'focus' ? state.restore : state.current,
    };
  }
  return { current: next, restore: next };
}

export function exitWritingFocus(state: WritingViewState): WritingViewState {
  if (state.current !== 'focus') return state;
  return { current: state.restore, restore: state.restore };
}

export function writingChapterSwitchLocked(
  revisionBusy: boolean,
  reviewBusy: 'sync' | 'decision' | null,
) {
  return revisionBusy || reviewBusy !== null;
}
