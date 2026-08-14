import { describe, expect, it } from 'vitest';
import { defaultWorkflow } from './defaultWorkflow';

describe('default LangGraph workflow contract', () => {
  it('uses the eight vNext artifacts and joins text and cover at export', () => {
    expect(defaultWorkflow.name).toBe('长篇小说生产线工作流');
    expect(defaultWorkflow.version).toBe('27.1.0-langgraph-native');
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
      description: '单章纯文本输出，篇幅只服从冻结软目标与当前施工图。',
    });
    expect(text?.input_schema.map((field) => field.key)).toEqual(['pov']);
    const detail = defaultWorkflow.nodes.find((node) => node.id === 'detail');
    const volumes = defaultWorkflow.nodes.find((node) => node.id === 'volumes');
    const brief = defaultWorkflow.nodes.find((node) => node.id === 'brief');
    expect(brief?.input_schema.map((field) => field.key)).toEqual(expect.arrayContaining([
      'word_target_soft',
      'chapter_target_soft',
    ]));
    expect(brief?.input_schema.map((field) => field.key)).not.toEqual(expect.arrayContaining([
      'chapter_min_reasonable',
      'chapter_max_reasonable',
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
