import { describe, expect, it } from 'vitest';
import {
  frozenCoverAssetBindingFixture,
  frozenProviderBindingsFixture,
} from '../contracts/runTestFixtures';
import type { GraphRunDefinition } from '../contracts';
import { defaultWorkflow } from '../state/defaultWorkflow';
import { DEFAULT_CAPACITY_POLICY } from '../lib/narrativeScale';
import { frozenBindingInventory } from './frozenBindingInventory';

function definition(qualityMode: GraphRunDefinition['quality_mode']): GraphRunDefinition {
  return {
    architecture_version: 'phase27-vnext',
    run_id: 'run-1',
    project_id: 'project-1',
    workflow_id: 'official-deepseek-deep',
    workflow_revision: '28.0.0-official-deepseek',
    workflow_digest: 'a'.repeat(64),
    quality_mode: qualityMode,
    inputs: {},
    scale_profile: {
      word_target_soft: 100_000,
      detail_segment_char_cap: 12_000,
      volume_candidate_cap: 8,
      json_item_caps: {},
      capacity_policy: DEFAULT_CAPACITY_POLICY,
    },
    provider_bindings: frozenProviderBindingsFixture(),
    cover_asset_binding: frozenCoverAssetBindingFixture(),
    export_preferences: { format: 'zip', author: '', version_note: '' },
    branch_origin: null,
    created_at: '2026-08-15T00:00:00Z',
  };
}

describe('frozenBindingInventory', () => {
  it('derives a read-only inventory from the frozen Run definition', () => {
    const items = frozenBindingInventory(definition('balanced'), defaultWorkflow);
    expect(items).toHaveLength(8);
    expect(items[0]).toMatchObject({
      id: 'brief',
      model: 'deepseek-v4-pro',
      prompt: `prompt-brief · ${'a'.repeat(12)}`,
    });
    expect(items[items.length - 1]).toMatchObject({
      id: 'cover-image',
      model: 'gpt-image-2',
    });
    expect(items.find((item) => item.id === 'text')?.writeback).toContain('Canon / Wiki');
  });

  it('makes the deep prose review requirement explicit without becoming editable config', () => {
    const text = frozenBindingInventory(definition('deep'), defaultWorkflow)
      .find((item) => item.id === 'text');
    expect(text?.review).toContain('文风');
    expect(text?.review).not.toContain('建议审');
  });
});
