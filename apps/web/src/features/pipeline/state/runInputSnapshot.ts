import type { RunInputs } from '../contracts';

export function isRunInputs(value: unknown): value is RunInputs {
  if (!value || typeof value !== 'object') return false;
  const candidate = value as Partial<RunInputs>;
  return typeof candidate.title === 'string'
    && typeof candidate.theme === 'string'
    && (candidate.quality_mode === 'fast' || candidate.quality_mode === 'balanced' || candidate.quality_mode === 'deep')
    && hasValidLengthEnvelope(candidate.length_envelope)
    && Boolean(candidate.run_intent && typeof candidate.run_intent === 'object');
}

function hasValidLengthEnvelope(value: unknown): boolean {
  if (!value || typeof value !== 'object') return false;
  const envelope = value as RunInputs['length_envelope'];
  const optionalPositive = (item: unknown) => item == null || (Number.isInteger(item) && Number(item) > 0);
  return optionalPositive(envelope.word_target_soft)
    && optionalPositive(envelope.chapter_target_soft)
    && Object.keys(envelope).every((key) => key === 'word_target_soft' || key === 'chapter_target_soft');
}
