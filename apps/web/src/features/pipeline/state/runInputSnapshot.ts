import type { RunInputs } from '../contracts';

/**
 * A new local session holds a BookScaleTarget until the server freezes it.
 * Server snapshots hold the derived BookScalePlan. The two shapes are
 * mutually exclusive lifecycle contracts.
 */
export function isRunInputs(value: unknown): value is RunInputs {
  if (!value || typeof value !== 'object') return false;
  const candidate = value as Partial<RunInputs>;
  return typeof candidate.title === 'string'
    && typeof candidate.theme === 'string'
    && (candidate.quality_mode === 'fast' || candidate.quality_mode === 'balanced' || candidate.quality_mode === 'deep')
    && hasValidScaleContract(candidate)
    && Boolean(candidate.run_intent && typeof candidate.run_intent === 'object');
}

function hasValidScaleContract(candidate: Partial<RunInputs>): boolean {
  const target = candidate.book_scale_target;
  const plan = candidate.book_scale_plan;
  const validTarget = Boolean(
    target
    && (target.target_mode === 'total_chars' || target.target_mode === 'total_chapters')
    && Number.isInteger(target.target_value)
    && target.target_value > 0,
  );
  const validPlan = plan?.contract_version === 'book-scale-plan-v1';
  return validTarget !== validPlan;
}
