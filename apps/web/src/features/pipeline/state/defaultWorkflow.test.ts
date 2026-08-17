import { describe, expect, it } from 'vitest';
import { defaultWorkflow } from './defaultWorkflow';

describe('default LangGraph workflow contract', () => {
  it('uses the eight vNext artifacts and joins text and cover at export', () => {
    expect(defaultWorkflow.name).toBe('DeepSeek 平衡创作流水线');
    expect(defaultWorkflow.version).toBe('29.34.0-first-pass-causal-planning');
    expect(defaultWorkflow.nodes.find((node) => node.id === 'spine')?.model_settings.temperature).toBe(0.45);
    expect(defaultWorkflow.nodes.find((node) => node.id === 'cast')?.model_settings.temperature).toBe(0.55);
    expect(defaultWorkflow.nodes.find((node) => node.id === 'detail')?.model_settings.temperature).toBe(0.3);
    expect(defaultWorkflow.edges).toEqual(expect.arrayContaining([
      { id: 'e-detail-text', source: 'detail', target: 'text' },
      { id: 'e-detail-cover', source: 'detail', target: 'cover' },
      { id: 'e-text-export', source: 'text', target: 'export' },
      { id: 'e-cover-export', source: 'cover', target: 'export' },
    ]));
    expect(defaultWorkflow.edges).not.toContainEqual(expect.objectContaining({ source: 'text', target: 'cover' }));
    const cover = defaultWorkflow.nodes.find((node) => node.id === 'cover');
    const text = defaultWorkflow.nodes.find((node) => node.id === 'text');
    expect(text?.generation_budget).toEqual({
      max_tokens: 6000,
      description: '按冻结场景顺序逐场生成；场景按戏剧负载使用滚动字符区间，整章命中质量档位长度合同，越界最多三次有界重写。',
    });
    expect(text?.input_schema.map((field) => field.key)).toEqual(['pov']);
    const detail = defaultWorkflow.nodes.find((node) => node.id === 'detail');
    const volumes = defaultWorkflow.nodes.find((node) => node.id === 'volumes');
    const brief = defaultWorkflow.nodes.find((node) => node.id === 'brief');
    const briefFields = new Map(brief?.input_schema.map((field) => [field.key, field]));
    expect(brief?.model_settings.model).toBe('deepseek-v4-pro');
    expect(briefFields.get('core_concept')?.required).toBe(true);
    expect(briefFields.get('genre')?.default).toBe('自动判断');
    expect(['audience', 'keywords', 'taboos'].map((key) => briefFields.get(key)?.required)).toEqual([
      false, false, false,
    ]);
    expect(brief?.input_schema.map((field) => field.key)).toEqual(expect.arrayContaining([
      'word_target_soft',
    ]));
    expect(brief?.input_schema.map((field) => field.key)).not.toEqual(expect.arrayContaining([
      'chapter_target_soft',
      'chapter_min_reasonable',
      'chapter_max_reasonable',
      'volume_target_override',
    ]));
    expect(volumes?.input_schema.map((field) => field.key)).toEqual(['conflict_density']);
    expect(detail?.input_schema.map((field) => field.key)).toEqual(['must_include']);
    expect(detail?.generation_budget?.description).toContain('Spine 因果边界');
    expect(defaultWorkflow.nodes.map((node) => node.id)).toEqual([
      'brief', 'spine', 'cast', 'volumes', 'detail', 'text', 'cover', 'export',
    ]);
    expect(detail?.label).toBe('章节施工图');
    const derivedOnlyKeys = ['params', 'input_refs', 'output_key', 'memory_policy', 'output_schema', 'quality_policy'];
    expect(defaultWorkflow.nodes.every((node) => derivedOnlyKeys.every((key) => !(key in node)))).toBe(true);
    expect(cover?.image_provider_profile_id).toBe('openai-compatible-image');
  });
});
