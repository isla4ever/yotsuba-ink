import type { RunInputs } from '../contracts';

export function isRunInputs(value: unknown): value is RunInputs {
  if (!value || typeof value !== 'object') return false;
  const candidate = value as Partial<RunInputs>;
  return typeof candidate.project_id === 'string'
    && (candidate.quality_mode === 'fast' || candidate.quality_mode === 'balanced' || candidate.quality_mode === 'deep')
    && hasValidLengthEnvelope(candidate.length_envelope)
    && Boolean(candidate.run_intent && typeof candidate.run_intent === 'object')
    && Boolean(candidate.export_preferences && typeof candidate.export_preferences === 'object');
}

function hasValidLengthEnvelope(value: unknown): boolean {
  if (!value || typeof value !== 'object') return false;
  const envelope = value as RunInputs['length_envelope'];
  return Number.isInteger(envelope.word_target_soft)
    && envelope.word_target_soft > 0
    && Object.keys(envelope).every((key) => key === 'word_target_soft');
}
