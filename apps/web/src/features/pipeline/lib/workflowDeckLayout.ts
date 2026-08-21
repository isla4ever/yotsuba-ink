export type WorkflowDeckPose = {
  x: number
  z: number
}

const clamp = (minimum: number, value: number, maximum: number) =>
  Math.min(maximum, Math.max(minimum, value))

const screenFacingAngle = 22

export function workflowDeckLayer(index: number, itemCount: number) {
  return 70 + Math.min(index, Math.max(0, itemCount - 1))
}

export function workflowDeckPose(
  index: number,
  viewportWidth: number,
  itemCount: number,
): WorkflowDeckPose {
  const safeWidth = Math.max(320, viewportWidth)
  const safeCount = Math.max(1, itemCount)
  const sheetWidth = clamp(118, safeWidth * 0.14, 168)
  const projectedWidth =
    sheetWidth * Math.cos((screenFacingAngle * Math.PI) / 180)
  const edgePadding = clamp(24, safeWidth * 0.03, 44)
  const availableSpan = Math.max(
    0,
    safeWidth - projectedWidth - edgePadding * 2,
  )
  const step =
    safeCount > 1
      ? Math.min(availableSpan / (safeCount - 1), sheetWidth * 0.84)
      : 0
  const span = step * Math.max(0, safeCount - 1)
  const depthIndex = safeCount - index - 1

  return {
    x: -span / 2 + index * step,
    z: depthIndex === 0 ? 0 : -depthIndex * 2,
  }
}
