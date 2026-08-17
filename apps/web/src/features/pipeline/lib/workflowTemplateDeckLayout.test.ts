import { describe, expect, it } from 'vitest';
import { workflowTemplateDeckLayer, workflowTemplateDeckPose } from './workflowTemplateDeckLayout';

describe('workflowTemplateDeckLayout', () => {
  it('keeps all stage sheets ordered inside a bounded desktop span', () => {
    const poses = Array.from({ length: 8 }, (_, index) => workflowTemplateDeckPose(index, 820, 8));

    expect(poses.map((pose) => pose.x)).toEqual([...poses.map((pose) => pose.x)].sort((a, b) => a - b));
    expect(poses[0]?.x).toBeGreaterThan(-410);
    expect(poses[7]?.x).toBeLessThan(410);
    expect(poses.every((pose) => pose.rotationY === 22)).toBe(true);
  });

  it('layers later manuscript sheets above earlier sheets', () => {
    expect(workflowTemplateDeckLayer(7, 8)).toBeGreaterThan(workflowTemplateDeckLayer(0, 8));
  });
});
