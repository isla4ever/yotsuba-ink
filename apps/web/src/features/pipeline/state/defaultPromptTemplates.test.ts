import { describe, expect, it } from 'vitest';
import contract from '../../../../test-fixtures/prompt-material-contract.json';
import { defaultPromptTemplates, promptMaterialKeys } from './defaultPromptTemplates';

describe('default Prompt material contract', () => {
  it('keeps frontend Prompt variables aligned with the Graph Context contract', () => {
    expect(promptMaterialKeys).toEqual(contract);
    expect(Object.fromEntries(defaultPromptTemplates.map((template) => [
      template.stage_type,
      template.variables,
    ]))).toEqual(contract);
  });

  it('keeps chapter version identity outside Provider output', () => {
    const textPrompt = defaultPromptTemplates.find((template) => template.stage_type === 'text');

    expect(textPrompt?.content).toContain('不得返回由 LangGraph 运行时持有的 version_id');
  });
});
