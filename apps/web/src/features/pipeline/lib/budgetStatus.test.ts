import { describe, expect, it } from 'vitest';
import { latestBudgetAlert } from './budgetStatus';
import type { RunEvent } from '../contracts';

describe('latestBudgetAlert (D5)', () => {
  it('returns null without budget events and ignores non-budget manual interventions', () => {
    expect(latestBudgetAlert([])).toBeNull();
    expect(latestBudgetAlert([
      { type: 'manual_intervention_required', run_id: 'r', reason: '质量阻断' },
      { type: 'chapter_delta', run_id: 'r', node_id: 'text' },
    ] as RunEvent[])).toBeNull();
  });

  it('maps warnings with writer-language copy (no Token wording) and usage percent', () => {
    const alert = latestBudgetAlert([
      { type: 'stage_budget_warning', run_id: 'r', node_id: 'text', used_tokens: 8000, max_tokens: 10000 },
    ] as RunEvent[]);
    expect(alert).toMatchObject({ scope: 'stage', severity: 'warning', stageId: 'text' });
    expect(alert?.message).toContain('用量额度');
    expect(alert?.message).toContain('80%');
    expect(alert?.message).not.toContain('Token');
  });

  it('lets the newest event win: exceeded after warning escalates, run scope detected', () => {
    const alert = latestBudgetAlert([
      { type: 'run_budget_exceeded', run_id: 'r', message: '本次运行 Token 预算已用尽' },
      { type: 'stage_budget_warning', run_id: 'r', node_id: 'text', used_tokens: 8000, max_tokens: 10000 },
    ] as RunEvent[]);
    expect(alert).toMatchObject({ scope: 'run', severity: 'exceeded' });
    expect(alert?.message).toContain('已用尽');
    expect(alert?.message).not.toContain('Token');
  });

  it('clears a stale exceeded bar once the creator resumed after adjusting the budget', () => {
    const events = [
      { type: 'run_resumed', run_id: 'r' },
      { type: 'run_budget_exceeded', run_id: 'r' },
    ] as RunEvent[];
    expect(latestBudgetAlert(events)).toBeNull();
    // Warnings keep showing across a resume (still approaching the limit)...
    const warned = latestBudgetAlert([
      { type: 'run_resumed', run_id: 'r' },
      { type: 'stage_budget_warning', run_id: 'r', node_id: 'text', used_tokens: 9000, max_tokens: 10000 },
    ] as RunEvent[]);
    expect(warned?.severity).toBe('warning');
    // ...and a fresh exceeded after the resume still surfaces.
    const relapsed = latestBudgetAlert([
      { type: 'run_budget_exceeded', run_id: 'r' },
      { type: 'run_resumed', run_id: 'r' },
    ] as RunEvent[]);
    expect(relapsed?.severity).toBe('exceeded');
  });

  it('treats budget-carrying manual interventions as exceeded', () => {
    const alert = latestBudgetAlert([
      {
        type: 'manual_intervention_required',
        run_id: 'r',
        node_id: 'cover',
        reason: '图片预算用尽',
        budget_state: { run_max_tokens: 1000 },
      },
    ] as RunEvent[]);
    expect(alert).toMatchObject({ scope: 'stage', severity: 'exceeded', stageId: 'cover' });
  });
});
