import { describe, expect, it } from 'vitest';
import { buildRunInputs } from './runInputs';
import { defaultWorkflow } from './defaultWorkflow';
import type { ProjectRecord } from '../contracts';

const project = {
  id: 'proj-42',
  title: '群星回响',
} as ProjectRecord;

describe('buildRunInputs (mine 4)', () => {
  it('takes title and project_id from the active project instead of a hardcoded book name', () => {
    const inputs = buildRunInputs(defaultWorkflow, 'backend', project);
    expect(inputs.title).toBe('群星回响');
    expect(inputs.project_id).toBe('proj-42');
    expect((inputs.run_intent.project_brief as { title?: string }).title).toBe('群星回响');
    expect(inputs.run_intent.project_brief.narrative_profile).toBe('故事建筑师');
    expect(inputs).not.toHaveProperty('execution_mode');
    expect(inputs.run_intent).not.toHaveProperty('mode_policy');
  });

  it('falls back to the title global input and freezes the Brief length envelope', () => {
    const inputs = buildRunInputs(defaultWorkflow, 'backend', null);
    const titleDefault = String(defaultWorkflow.global_inputs.find((item) => item.key === 'title')?.default ?? '');
    expect(inputs.title).toBe(titleDefault);
    expect(inputs.theme).toBe('旧港、记忆实验、群像、旧案');
    expect(inputs.project_id).toBe('');
    expect(inputs.length_envelope).toEqual({
      word_target_soft: 100000,
      chapter_target_soft: null,
    });
    expect(inputs).not.toHaveProperty('book_scale_plan');
    expect(inputs).not.toHaveProperty('stage_configs');
    expect(inputs.run_intent.knowledge_strategy).toMatchObject({ reference_mode: 'smart_search' });
    expect(inputs.run_intent).not.toHaveProperty('variant_strategy');
  });

  it('derives theme from the configured Brief-stage keywords', () => {
    const themed = {
      ...defaultWorkflow,
      nodes: defaultWorkflow.nodes.map((stage) => stage.id === 'brief' ? {
        ...stage,
        input_schema: stage.input_schema.map((field) => field.key === 'keywords'
          ? { ...field, default: ['蒸汽朋克', '家族史诗'] }
          : field),
      } : stage),
    };
    const inputs = buildRunInputs(themed, 'backend', project);
    expect(inputs.theme).toBe('蒸汽朋克、家族史诗');
    expect((inputs.run_intent.project_brief as { theme?: string }).theme).toBe('蒸汽朋克、家族史诗');
  });

  it('uses the workflow name when no project and no title default exist', () => {
    const untitled = {
      ...defaultWorkflow,
      global_inputs: defaultWorkflow.global_inputs.filter((item) => item.key !== 'title'),
    };
    const inputs = buildRunInputs(untitled, 'backend', null);
    expect(inputs.title).toBe(untitled.name);
  });
});
