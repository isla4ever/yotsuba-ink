import { describe, expect, it } from 'vitest';
import { defaultWorkflow } from './defaultWorkflow';

describe('default workflow delivery topology', () => {
  it('starts cover beside text after detail and joins both branches at export', () => {
    expect(defaultWorkflow.version).toBe('1.0.5-parallel-delivery');
    expect(defaultWorkflow.edges).toEqual(expect.arrayContaining([
      { id: 'e-detail-text', source: 'detail', target: 'text' },
      { id: 'e-detail-cover', source: 'detail', target: 'cover' },
      { id: 'e-text-export', source: 'text', target: 'export' },
      { id: 'e-cover-export', source: 'cover', target: 'export' },
    ]));
    expect(defaultWorkflow.edges).not.toContainEqual(expect.objectContaining({ source: 'text', target: 'cover' }));
    const cover = defaultWorkflow.nodes.find((node) => node.id === 'cover');
    expect(cover?.input_refs).toContain('detail_outline');
    expect(cover?.input_refs).not.toContain('chapters');
  });
});
