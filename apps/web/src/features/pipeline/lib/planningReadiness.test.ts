import { describe, expect, it } from 'vitest';
import { defaultWorkflow } from '../state/defaultWorkflow';
import { stageArtifactLabel, stageConfigurationReadiness } from './planningReadiness';

describe('planning readiness', () => {
  it('marks the seeded Story Brief ready', () => {
    const stage = defaultWorkflow.nodes.find((item) => item.id === 'brief');
    expect(stageConfigurationReadiness(stage!)).toMatchObject({ completed: 3, ready: true, total: 3 });
  });

  it('reports missing required fields without counting optional reference fields', () => {
    const stage = defaultWorkflow.nodes.find((item) => item.id === 'brief')!;
    const incomplete = {
      ...stage,
      input_schema: stage.input_schema.map((field) => (field.key === 'core_concept' ? { ...field, default: ' ' } : field)),
    };
    expect(stageConfigurationReadiness(incomplete)).toEqual({
      completed: 2,
      missingLabels: ['核心创意/冲突'],
      ready: false,
      total: 3,
    });
  });

  it('uses a stable business artifact label for every stage', () => {
    expect(defaultWorkflow.nodes.map(stageArtifactLabel)).toEqual([
      '创作契约、世界规则与长度包络',
      '因果转折、结局与开放问题',
      '人物职责、关系与出场窗口',
      '完整故事卷合同与叙事引用',
      '章节施工图、场景推进与交接',
      '章节正文定稿',
      '封面简报与选定资产',
      '版本选择与交付格式',
    ]);
  });
});
