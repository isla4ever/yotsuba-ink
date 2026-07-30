export type ArtifactDeckPose = {
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

const SCREEN_FACING_ANGLE_DEG = 22;
const SHEET_DEPTH_STEP_PX = 2;

export function artifactDeckLayer(index: number, itemCount: number) {
  return 70 + Math.min(index, Math.max(0, itemCount - 1));
}

export function artifactDeckPose(
  index: number,
  _selectedIndex: number,
  viewportWidth: number,
  itemCount: number,
): ArtifactDeckPose {
  const safeWidth = Math.max(320, viewportWidth);
  const safeCount = Math.max(1, itemCount);
  const sheetWidth = clamp(152, safeWidth * 0.17, 220);
  const projectedSheetWidth = sheetWidth * Math.cos(SCREEN_FACING_ANGLE_DEG * Math.PI / 180);
  const edgePadding = clamp(32, safeWidth * 0.03, 58);
  const availableSpan = Math.max(0, safeWidth - projectedSheetWidth - edgePadding * 2);
  const step = safeCount > 1
    ? Math.min(availableSpan / (safeCount - 1), sheetWidth * 0.78)
    : 0;
  const span = step * Math.max(0, safeCount - 1);
  const x = -span / 2 + index * step;
  const depthIndex = safeCount - index - 1;
  return {
    opacity: 1,
    rotationX: 0,
    rotationY: SCREEN_FACING_ANGLE_DEG,
    rotationZ: 0,
    scale: 1,
    x,
    y: 0,
    z: depthIndex === 0 ? 0 : -depthIndex * SHEET_DEPTH_STEP_PX,
  };
}
