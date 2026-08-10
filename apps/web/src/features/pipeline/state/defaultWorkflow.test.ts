import { describe, expect, it } from 'vitest';
import { defaultWorkflow } from './defaultWorkflow';

describe('default LangGraph workflow contract', () => {
  it('uses the eight vNext artifacts and joins text and cover at export', () => {
    expect(defaultWorkflow.name).toBe('长篇小说生产线工作流');
    expect(defaultWorkflow.version).toBe('26.1.0-langgraph-vnext');
    expect(defaultWorkflow.edges).toEqual(expect.arrayContaining([
      { id: 'e-detail-text', source: 'detail', target: 'text' },
      { id: 'e-detail-cover', source: 'detail', target: 'cover' },
      { id: 'e-text-export', source: 'text', target: 'export' },
      { id: 'e-cover-export', source: 'cover', target: 'export' },
    ]));
    expect(defaultWorkflow.edges).not.toContainEqual(expect.objectContaining({ source: 'text', target: 'cover' }));
    const cover = defaultWorkflow.nodes.find((node) => node.id === 'cover');
    const text = defaultWorkflow.nodes.find((node) => node.id === 'text');
    expect(text?.generation_budget).toMatchObject({ target_chars: 1700, min_chars: 1400, max_chars: 2200, max_tokens: 3600 });
    expect(text?.input_schema.map((field) => field.key)).toEqual(['pov']);
    const detail = defaultWorkflow.nodes.find((node) => node.id === 'detail');
    const outline = defaultWorkflow.nodes.find((node) => node.id === 'outline');
    const info = defaultWorkflow.nodes.find((node) => node.id === 'info');
    expect(info?.input_schema.map((field) => field.key)).toEqual(expect.arrayContaining([
      'book_scale_target_mode',
      'book_scale_target_value',
    ]));
    expect(outline?.input_schema.map((field) => field.key)).toEqual(['conflict_density']);
    expect(detail?.input_schema.map((field) => field.key)).toEqual(['must_include']);
    expect(detail?.generation_budget?.description).toContain('默认每章一个主场景');
    expect(defaultWorkflow.nodes.map((node) => node.id)).toEqual([
      'info', 'characters', 'summary', 'outline', 'detail', 'text', 'cover', 'export',
    ]);
    expect(detail?.label).toBe('章节施工图');
    const derivedOnlyKeys = ['params', 'input_refs', 'output_key', 'memory_policy', 'output_schema', 'quality_policy'];
    expect(defaultWorkflow.nodes.every((node) => derivedOnlyKeys.every((key) => !(key in node)))).toBe(true);
    expect(cover?.image_provider_profile_id).toBe('openai-compatible-image');
  });
});
