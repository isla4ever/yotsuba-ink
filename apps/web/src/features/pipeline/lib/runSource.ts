export type RunSource = 'backend';

export function getPreferredRunSource(): RunSource {
  return 'backend';
}

export function isBackendRunSource(source: RunSource) {
  return source === 'backend';
}
