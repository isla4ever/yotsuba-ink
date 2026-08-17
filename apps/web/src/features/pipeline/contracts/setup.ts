import type { KnowledgeDocument } from './knowledge';
import type { ProviderProfile, WorkflowDefinition } from './workflow';

/**
 * Project preparation is a two-step launch gate. Provider and stage bindings
 * belong to the separate workflow editor, not to the book planning surface.
 */
export type SetupStepId = 'story' | 'review';

export type SetupIssue = {
  code: string;
  severity: 'blocking' | 'warning';
  label: string;
  target: { stepId: SetupStepId; fieldId?: string };
};

export type SetupStep = {
  id: SetupStepId;
  label: string;
  status: 'complete' | 'current' | 'blocked' | 'pending';
  summary?: string;
  issues: SetupIssue[];
};

export type SetupFlowState = {
  activeStepId: SetupStepId;
  direction: 'forward' | 'backward' | 'none';
  submitState: 'idle' | 'validating' | 'creating-run' | 'failed';
  lastFocusedFieldId?: string;
};

export type ProviderReadinessCheck = {
  provider_id: string;
  provider_name: string;
  expected_kind: ProviderProfile['kind'];
  /** Effective model(s) used by the materialized workflow. */
  model?: string;
  used_by: string[];
  ready: boolean;
  issue_codes: string[];
  message: string;
};

export type ProviderReadinessReport = {
  ok: boolean;
  scope: 'configuration_only';
  checked_provider_count: number;
  checks: ProviderReadinessCheck[];
  message: string;
};

export type SetupDerivationInput = {
  workflow: WorkflowDefinition;
  knowledgeDocuments: KnowledgeDocument[];
  readiness?: ProviderReadinessReport;
};

export type SettingsSectionId =
  | 'story'
  | 'references'
  | 'creation-mode'
  | 'ai-service'
  | 'stage-exceptions';

export type SettingsSectionSummary = {
  id: SettingsSectionId;
  title: string;
  summary: string[];
  status: 'ready' | 'warning' | 'blocked' | 'informational';
  action?: { label: string; target: string };
};
