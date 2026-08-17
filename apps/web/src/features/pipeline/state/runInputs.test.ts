import { describe, expect, it } from 'vitest';
import type { ProjectRecord } from '../contracts';
import { defaultWorkflow } from './defaultWorkflow';
import { buildRunInputs } from './runInputs';

const project = { id: 'proj-42' } as ProjectRecord;

describe('buildRunInputs', () => {
  it('carries project ownership and Brief configuration without a user-supplied title', () => {
    const inputs = buildRunInputs(defaultWorkflow, 'backend', project);
    expect(inputs.project_id).toBe('proj-42');
    expect(inputs).not.toHaveProperty('title');
    expect(inputs).not.toHaveProperty('theme');
    expect(inputs.run_intent.project_brief).toMatchObject({
      narrative_profile: '故事建筑师',
      core_concept: expect.any(String),
    });
    expect(inputs).not.toHaveProperty('execution_mode');
  });

  it('freezes the Brief length envelope and knowledge strategy', () => {
    const inputs = buildRunInputs(defaultWorkflow, 'backend', null);
    expect(inputs.project_id).toBe('');
    expect(inputs.length_envelope).toEqual({
      word_target_soft: 100000,
    });
    expect(inputs).not.toHaveProperty('book_scale_plan');
    expect(inputs).not.toHaveProperty('stage_configs');
    expect(inputs.run_intent.knowledge_strategy).toMatchObject({ reference_mode: 'smart_search' });
  });

  it('preserves configured Brief keywords as structured project intent', () => {
    const configured = {
      ...defaultWorkflow,
      nodes: defaultWorkflow.nodes.map((stage) => stage.id === 'brief' ? {
        ...stage,
        input_schema: stage.input_schema.map((field) => field.key === 'keywords'
          ? { ...field, default: ['蒸汽朋克', '家族史诗'] }
          : field),
      } : stage),
    };
    const inputs = buildRunInputs(configured, 'backend', project);
    expect(inputs.run_intent.project_brief.keywords).toEqual(['蒸汽朋克', '家族史诗']);
  });
});
