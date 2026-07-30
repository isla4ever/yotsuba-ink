export type CharacterGraphViewportInput = {
  containerHeight: number;
  containerWidth: number;
  viewportHeight: number;
  viewportWidth: number;
};

const clamp = (value: number, min: number, max: number) => Math.min(max, Math.max(min, value));

export function characterGraphViewport({
  containerHeight,
  containerWidth,
  viewportHeight,
  viewportWidth,
}: CharacterGraphViewportInput) {
  const safeViewportHeight = Math.max(360, Math.floor(viewportHeight));
  const heightLimit = viewportWidth <= 720
    ? Math.min(360, Math.floor(safeViewportHeight * 0.4))
    : viewportWidth <= 1180
      ? Math.min(440, Math.floor(safeViewportHeight * 0.52))
      : Math.min(760, Math.floor(safeViewportHeight * 0.72));

  return {
    height: clamp(Math.floor(containerHeight || heightLimit), 180, Math.max(180, heightLimit)),
    width: Math.max(180, Math.floor(containerWidth)),
  };
}
