import { Check, LockKeyhole } from 'lucide-react';

export type RefChipOption = { id: string; label: string; hint?: string };

type Props = {
  ariaLabel: string;
  /** ids that must stay selected (e.g. the chapter POV inside cast_ids). */
  lockedIds?: string[];
  onChange: (ids: string[]) => void;
  options: RefChipOption[];
  readOnly: boolean;
  selected: string[];
};

/**
 * Structured reference picker for frozen upstream ids (spine turns, cast
 * subjects). Selection order follows the option registry so downstream
 * continuity checks receive deterministic id sequences.
 */
export function ArtifactRefChips({ ariaLabel, lockedIds = [], onChange, options, readOnly, selected }: Props) {
  const knownIds = new Set(options.map((option) => option.id));
  const unknownIds = selected.filter((id) => !knownIds.has(id));
  const toggle = (id: string) => {
    const next = selected.includes(id)
      ? selected.filter((item) => item !== id)
      : [...selected, id];
    onChange([
      ...options.filter((option) => next.includes(option.id)).map((option) => option.id),
      ...next.filter((id) => !knownIds.has(id)),
    ]);
  };
  return (
    <div aria-label={ariaLabel} className="vnext-ref-chips" role="group">
      {options.map((option) => {
        const active = selected.includes(option.id);
        const locked = lockedIds.includes(option.id);
        return (
          <button
            aria-pressed={active}
            className={`vnext-ref-chip${active ? ' active' : ''}${locked ? ' locked' : ''}`}
            disabled={readOnly || locked}
            key={option.id}
            onClick={() => toggle(option.id)}
            title={option.hint ?? option.label}
            type="button"
          >
            {locked ? <LockKeyhole aria-hidden="true" size={12} /> : active ? <Check aria-hidden="true" size={12} /> : null}
            {option.label}
          </button>
        );
      })}
      {unknownIds.map((id) => (
        <span className="vnext-ref-chip unknown" key={id} title="引用了当前注册表之外的 ID">{id}</span>
      ))}
    </div>
  );
}
