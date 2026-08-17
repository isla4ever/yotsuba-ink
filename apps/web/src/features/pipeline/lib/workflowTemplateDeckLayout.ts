export type WorkflowTemplateDeckPose = {
  opacity: number;
  rotationX: number;
  rotationY: number;
  rotationZ: number;
  scale: number;
  x: number;
  y: number;
  z: number;
};

const clamp = (minimum: number, value: number, maximum: number) => (
  Math.min(maximum, Math.max(minimum, value))
);

const screenFacingAngle = 22;
const sheetDepthStep = 2;

export function workflowTemplateDeckLayer(index: number, itemCount: number) {
  return 70 + Math.min(index, Math.max(0, itemCount - 1));
}

export function workflowTemplateDeckPose(
  index: number,
  viewportWidth: number,
  itemCount: number,
): WorkflowTemplateDeckPose {
  const safeWidth = Math.max(320, viewportWidth);
  const safeCount = Math.max(1, itemCount);
  const sheetWidth = clamp(118, safeWidth * 0.14, 168);
  const projectedWidth = sheetWidth * Math.cos(screenFacingAngle * Math.PI / 180);
  const edgePadding = clamp(24, safeWidth * 0.03, 44);
  const availableSpan = Math.max(0, safeWidth - projectedWidth - edgePadding * 2);
  const step = safeCount > 1
    ? Math.min(availableSpan / (safeCount - 1), sheetWidth * 0.84)
    : 0;
  const span = step * Math.max(0, safeCount - 1);
  const depthIndex = safeCount - index - 1;

  return {
    opacity: 1,
    rotationX: 0,
    rotationY: screenFacingAngle,
    rotationZ: 0,
    scale: 1,
    x: -span / 2 + index * step,
    y: 0,
    z: depthIndex === 0 ? 0 : -depthIndex * sheetDepthStep,
  };
}

export function workflowTemplateDeckPoseVars(pose: WorkflowTemplateDeckPose) {
  return {
    autoAlpha: pose.opacity,
    force3D: true,
    rotationX: pose.rotationX,
    rotationY: pose.rotationY,
    rotationZ: pose.rotationZ,
    scale: pose.scale,
    transformOrigin: '50% 50%',
    x: pose.x,
    xPercent: -50,
    y: pose.y,
    yPercent: -50,
    z: pose.z,
  };
}
