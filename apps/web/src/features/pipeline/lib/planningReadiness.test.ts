import { describe, expect, it } from 'vitest';
import { defaultWorkflow } from '../state/defaultWorkflow';
import { stageArtifactLabel, stageConfigurationReadiness } from './planningReadiness';

describe('planning readiness', () => {
  it('marks the seeded Info brief ready', () => {
    const stage = defaultWorkflow.nodes.find((item) => item.id === 'info');
    expect(stageConfigurationReadiness(stage!)).toMatchObject({ completed: 8, ready: true, total: 8 });
  });

  it('reports missing required fields without counting optional reference fields', () => {
    const stage = defaultWorkflow.nodes.find((item) => item.id === 'info')!;
    const incomplete = {
      ...stage,
      input_schema: stage.input_schema.map((field) => (field.key === 'core_concept' ? { ...field, default: ' ' } : field)),
    };
    expect(stageConfigurationReadiness(incomplete)).toEqual({
      completed: 7,
      missingLabels: ['核心创意/冲突'],
      ready: false,
      total: 8,
    });
  });

  it('uses a stable business artifact label for every stage', () => {
    expect(defaultWorkflow.nodes.map(stageArtifactLabel)).toEqual([
      '立项设定与人物关系',
      '完整梗概与故事结构',
      '分卷节拍与冲突推进',
      '章节施工图与伏笔矩阵',
      '章节正文与修订版本',
      '封面方案与视觉提示词',
      '校验清单与交付文件包',
    ]);
  });
});
