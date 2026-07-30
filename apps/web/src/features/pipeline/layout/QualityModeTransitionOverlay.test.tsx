import { renderToStaticMarkup } from 'react-dom/server';
import { describe, expect, it } from 'vitest';
import {
  MODE_NOTICE_DWELL_MS,
  MODE_NOTICE_ENTER_MS,
  MODE_NOTICE_EXIT_MS,
  ModeTransitionScene,
  modeNoticeTiming,
} from './QualityModeTransitionOverlay';
import { qualityModeProfiles } from '../lib/qualityModes';
import type { QualityMode } from '../contracts';

function renderScene(mode: QualityMode | null, reducedMotion = false) {
  return renderToStaticMarkup(<ModeTransitionScene mode={mode} reducedMotion={reducedMotion} />);
}

describe('QualityModeTransitionOverlay badge', () => {
  it('renders nothing without an active notice', () => {
    expect(renderScene(null)).toBe('');
  });

  it('shows profile copy from qualityModeProfiles for every mode', () => {
    for (const mode of ['fast', 'balanced', 'deep'] as const) {
      const markup = renderScene(mode);
      expect(markup).toContain(qualityModeProfiles[mode].title);
      expect(markup).toContain(qualityModeProfiles[mode].intervention);
      expect(markup).toContain(`quality-mode-transition-overlay mode-${mode}`);
      expect(markup).toContain('role="status"');
    }
  });

  it('keeps the scene non-interactive and draws glyph strokes as one-shot pathLength shapes', () => {
    const markup = renderScene('fast');
    // Three feather chevrons, normalized for the 240ms draw-in; never infinite.
    expect(markup.match(/pathLength="1"/g)).toHaveLength(3);
    expect(markup).toContain('glyph-step-3');
    expect(markup).not.toContain('infinite');
    expect(renderScene('balanced').match(/pathLength="1"/g)).toHaveLength(2);
  });

  it('locks the 180/900/120 badge rhythm and zeroes it under reduced motion', () => {
    expect(MODE_NOTICE_ENTER_MS).toBe(180);
    expect(MODE_NOTICE_DWELL_MS).toBe(900);
    expect(MODE_NOTICE_EXIT_MS).toBe(120);
    expect(modeNoticeTiming(false)).toEqual({ enter: 180, exit: 120 });
    expect(modeNoticeTiming(true)).toEqual({ enter: 0, exit: 0 });
  });
});
