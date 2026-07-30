import { describe, expect, it } from 'vitest';
import { artifactDeckLayer, artifactDeckPose } from './artifactDeckLayout';

describe('artifactDeckPose', () => {
  it('keeps every sheet on one aligned right-facing plane', () => {
    const poses = Array.from({ length: 7 }, (_, index) => artifactDeckPose(index, 3, 1158, 7));
    expect(poses[3]).toMatchObject({ opacity: 1, rotationY: 22, scale: 1, y: 0, z: -6 });
    expect(poses[2].x).toBeLessThan(poses[3].x);
    expect(poses[4].x).toBeGreaterThan(poses[3].x);
    expect(poses.every((pose) => pose.rotationY === 22)).toBe(true);
    expect(poses.every((pose) => pose.rotationX === 0 && pose.rotationZ === 0)).toBe(true);
    expect(poses.every((pose) => pose.y === 0)).toBe(true);
    expect(poses.map((pose) => pose.z)).toEqual([-12, -10, -8, -6, -4, -2, 0]);
    expect(poses.every((pose) => pose.scale === 1)).toBe(true);
  });

  it('does not reorder the manuscript stack when selection changes', () => {
    const firstSelected = Array.from({ length: 7 }, (_, index) => artifactDeckPose(index, 0, 1158, 7));
    const lastSelected = Array.from({ length: 7 }, (_, index) => artifactDeckPose(index, 6, 1158, 7));
    expect(firstSelected.map((pose) => pose.x)).toEqual([...firstSelected.map((pose) => pose.x)].sort((a, b) => a - b));
    expect(lastSelected.map((pose) => pose.x)).toEqual([...lastSelected.map((pose) => pose.x)].sort((a, b) => a - b));
    expect(firstSelected.map((pose) => pose.x)).toEqual(lastSelected.map((pose) => pose.x));
    expect(firstSelected.map((pose) => pose.z)).toEqual(lastSelected.map((pose) => pose.z));
    expect(firstSelected.map((pose) => pose.scale)).toEqual(lastSelected.map((pose) => pose.scale));
    expect(firstSelected.every((pose) => pose.opacity === 1)).toBe(true);
    expect(lastSelected.every((pose) => pose.opacity === 1)).toBe(true);
    expect(firstSelected[6].x - firstSelected[0].x).toBeGreaterThan(880);
    expect(firstSelected[6].x - firstSelected[0].x).toBeLessThan(910);
    expect(Math.max(...firstSelected.map((pose) => Math.abs(pose.x)))).toBeLessThan(500);
  });

  it('keeps the rightward manuscript layering stable without selection reordering', () => {
    const layers = Array.from({ length: 7 }, (_, index) => artifactDeckLayer(index, 7));
    expect(layers).toEqual([...layers].sort((a, b) => a - b));
    expect(new Set(layers).size).toBe(7);
  });

  it('compresses the fan at narrow desktop widths without pushing endpoints off-canvas', () => {
    const poses = Array.from({ length: 7 }, (_, index) => artifactDeckPose(index, 6, 640, 7));
    expect(poses[6].x).toBeLessThan(225);
    expect(Math.min(...poses.map((pose) => pose.x))).toBeGreaterThan(-225);
    expect(poses.map((pose) => pose.x)).toEqual([...poses.map((pose) => pose.x)].sort((a, b) => a - b));
  });
});
