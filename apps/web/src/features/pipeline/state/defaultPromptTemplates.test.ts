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

    expect(textPrompt?.content).toContain('不得返回 version_id');
  });

  it('keeps Cast debut windows on the exact frozen chapter target', () => {
    const castPrompt = defaultPromptTemplates.find((template) => template.stage_type === 'cast');

    expect(castPrompt?.content).toContain('scale_plan.chapter_target');
    expect(castPrompt?.content).not.toContain('chapter_target 只是建议');
    expect(castPrompt?.content).toContain('严禁把 turn-N 直接抄成 chapter:N');
    expect(castPrompt?.content).toContain('机构职责默认保持机构形态');
    expect(castPrompt?.content).toContain('subject_refs.subject_mode 是冻结硬合同');
    expect(castPrompt?.content).toContain('不得虚构当下行动、当下说话或 POV');
    expect(castPrompt?.content).toContain('conflict_history');
    expect(castPrompt?.content).toContain('present_stakes');
    expect(castPrompt?.content).toContain('irreducibility');
  });

  it('keeps Detail chapter layout creative and runtime-bound', () => {
    const detailPrompt = defaultPromptTemplates.find((template) => template.stage_type === 'detail');

    expect(detailPrompt?.content).toContain('dramatic_job');
    expect(detailPrompt?.content).toContain('不是总字数除法');
    expect(detailPrompt?.content).toContain('Provider 不返回也不重新分配');
    expect(detailPrompt?.content).not.toContain('phase=cause');
    expect(detailPrompt?.content).not.toContain('每章只含 title、turn_refs');
  });

  it('keeps Brief strategic and Spine milestones dynamically scaled', () => {
    const briefPrompt = defaultPromptTemplates.find((template) => template.stage_type === 'brief');
    const spinePrompt = defaultPromptTemplates.find((template) => template.stage_type === 'spine');

    expect(briefPrompt?.content).toContain('不替 Spine 预写');
    expect(briefPrompt?.content).toContain('一次性障碍');
    expect(spinePrompt?.content).toContain('不机械切成五段等长');
    expect(spinePrompt?.content).toContain('40%-60%');
    expect(spinePrompt?.content).toContain('最后一个 turn 只落下余波');
  });
});
