import { describe, expect, it } from 'vitest';
import { defaultWorkflow } from '../state/defaultWorkflow';
import { stageArtifactLabel, stageConfigurationReadiness } from './planningReadiness';

describe('planning readiness', () => {
  it('marks the seeded Info brief ready', () => {
    const stage = defaultWorkflow.nodes.find((item) => item.id === 'info');
    expect(stageConfigurationReadiness(stage!)).toMatchObject({ completed: 9, ready: true, total: 9 });
  });

  it('reports missing required fields without counting optional reference fields', () => {
    const stage = defaultWorkflow.nodes.find((item) => item.id === 'info')!;
    const incomplete = {
      ...stage,
      input_schema: stage.input_schema.map((field) => (field.key === 'core_concept' ? { ...field, default: ' ' } : field)),
    };
    expect(stageConfigurationReadiness(incomplete)).toEqual({
      completed: 8,
      missingLabels: ['核心创意/冲突'],
      ready: false,
      total: 9,
    });
  });

  it('uses a stable business artifact label for every stage', () => {
    expect(defaultWorkflow.nodes.map(stageArtifactLabel)).toEqual([
      '创作契约与世界规则',
      '人物职责、关系与出场窗口',
      '故事脊柱与人物结局',
      '分卷节拍与叙事窗口',
      '章节施工图、义务与交接',
      '章节正文定稿',
      '封面简报与选定资产',
      '版本选择与交付格式',
    ]);
  });
});
