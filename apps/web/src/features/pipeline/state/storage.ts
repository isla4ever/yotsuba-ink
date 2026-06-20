import type { CanvasLayout, WorkflowDefinition } from '../types/workflow';
import { applyQualityMode } from '../utils/workflow';

export const canvasLayoutStorageKey = 'novel-workflow-canvas-layout';
export const qualityModeStorageKey = 'novel-workflow-quality-mode';

export function workflowWithStoredPreferences(workflow: WorkflowDefinition): WorkflowDefinition {
  return workflowWithStoredQualityMode(workflowWithStoredCanvasLayout(workflow));
}

export function workflowWithStoredQualityMode(workflow: WorkflowDefinition): WorkflowDefinition {
  try {
    const stored = window.localStorage.getItem(qualityModeStorageKey);
    if (stored !== 'fast' && stored !== 'balanced' && stored !== 'deep') return workflow;
    return applyQualityMode(workflow, stored);
  } catch {
    return workflow;
  }
}

export function workflowWithStoredCanvasLayout(workflow: WorkflowDefinition): WorkflowDefinition {
  try {
    const stored = window.localStorage.getItem(canvasLayoutStorageKey);
    if (!stored) return workflow;
    const canvas_layout = JSON.parse(stored) as CanvasLayout;
    if (!canvas_layout || typeof canvas_layout !== 'object' || !canvas_layout.nodes) return workflow;
    return {
      ...workflow,
      canvas_layout: { ...workflow.canvas_layout, ...canvas_layout, nodes: normalizeStoredCanvasNodes(workflow, canvas_layout.nodes) },
    };
  } catch {
    return workflow;
  }
}

function normalizeStoredCanvasNodes(workflow: WorkflowDefinition, nodes: CanvasLayout['nodes']) {
  const next = { ...(workflow.canvas_layout?.nodes ?? {}), ...nodes };
  if (!nodes['wiki-layer'] || isNear(nodes['wiki-layer'].x, 70) || isNear(nodes['wiki-layer'].x, 300)) {
    next['wiki-layer'] = workflow.canvas_layout?.nodes?.['wiki-layer'] ?? { x: 276, y: 302 };
  }
  if (!nodes['quality-layer'] || isNear(nodes['quality-layer'].x, 760) || isNear(nodes['quality-layer'].x, 694)) {
    next['quality-layer'] = workflow.canvas_layout?.nodes?.['quality-layer'] ?? { x: 694, y: 302 };
  }
  return next;
}

function isNear(value: number, target: number) {
  return Math.abs(value - target) <= 4;
}

export function saveCanvasLayoutLocally(layout: CanvasLayout) {
  try {
    window.localStorage.setItem(canvasLayoutStorageKey, JSON.stringify(layout));
  } catch {
    // Ignore local storage failures; backend autosave still receives the layout.
  }
}

export function saveQualityModeLocally(mode: WorkflowDefinition['quality_mode']) {
  try {
    window.localStorage.setItem(qualityModeStorageKey, mode);
  } catch {
    // Ignore local storage failures; workflow autosave still receives the mode.
  }
}

export function hasOnlineTextProvider(workflow: WorkflowDefinition) {
  return workflow.provider_profiles.some((provider) => {
    if (!provider.enabled) return false;
    if (provider.kind === 'mock') return true;
    return provider.kind === 'openai-compatible' && provider.base_url.trim() && provider.api_key_env.trim();
  });
}
