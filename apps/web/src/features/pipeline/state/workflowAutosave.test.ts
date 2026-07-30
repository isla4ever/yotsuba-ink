import { describe, expect, it } from 'vitest';
import {
  createWorkflowAutosaveRevisionGate,
  createWorkflowAutosaveSuppressionGate,
} from './workflowAutosave';

describe('workflow autosave suppression gate', () => {
  it('suppresses every replay of a hydrated workflow until an immutable edit replaces it', () => {
    const gate = createWorkflowAutosaveSuppressionGate<object>();
    const historicalWorkflow = { id: 'historical' };

    gate.suppress(historicalWorkflow);

    expect(gate.shouldSuppress(historicalWorkflow)).toBe(true);
    expect(gate.shouldSuppress(historicalWorkflow)).toBe(true);

    const editedWorkflow = { ...historicalWorkflow };
    expect(gate.shouldSuppress(editedWorkflow)).toBe(false);
    expect(gate.shouldSuppress(editedWorkflow)).toBe(false);
  });

  it('uses object identity rather than workflow content', () => {
    const gate = createWorkflowAutosaveSuppressionGate<object>();
    const hydratedWorkflow = { id: 'same-id' };

    gate.suppress(hydratedWorkflow);

    expect(gate.shouldSuppress({ id: 'same-id' })).toBe(false);
  });
});

describe('workflow autosave revision gate', () => {
  it('invalidates an older save result during historical workflow hydration', () => {
    const gate = createWorkflowAutosaveRevisionGate();
    const pendingSave = gate.begin();

    gate.invalidate();

    expect(gate.isCurrent(pendingSave)).toBe(false);
    const nextSave = gate.begin();
    expect(gate.isCurrent(nextSave)).toBe(true);
  });
});
