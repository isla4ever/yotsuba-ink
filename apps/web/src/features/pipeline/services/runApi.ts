import type { RunEvent, RunInputs } from '../contracts';

export async function resumeRun(runId: string) {
  await postWithoutBody(`/api/runs/${runId}/resume`);
}

export async function pauseRunRequest(runId: string) {
  await postWithoutBody(`/api/runs/${runId}/pause`);
}

export async function approveRunBrief(runId: string, artifact: string) {
  await postJson(`/api/runs/${runId}/approve-artifact`, {
    node_id: 'info',
    output_key: 'info_recommend',
    artifact,
  });
}

export async function regenerateRunBrief(
  runId: string,
  workflowId: string,
  inputs: RunInputs,
): Promise<{ artifact?: string }> {
  const response = await postJson(`/api/runs/${runId}/regenerate-brief`, {
    workflow_id: workflowId,
    inputs,
  });
  return response.json();
}

export async function createRunStream(workflowId: string, inputs: RunInputs) {
  const response = await postJson('/api/runs/stream', { workflow_id: workflowId, inputs });
  return response;
}

function postWithoutBody(url: string) {
  return fetch(url, { method: 'POST' });
}

function postJson(url: string, body: unknown) {
  return fetch(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
}

export function briefRegeneratedEvent(runId: string, artifact: string): RunEvent {
  return {
    type: 'brief_regenerated',
    run_id: runId,
    node_id: 'info',
    node_type: 'info_recommend',
    artifact,
  };
}
