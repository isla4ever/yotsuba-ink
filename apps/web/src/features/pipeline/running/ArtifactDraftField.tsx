import { useId, type ReactNode } from 'react';

export type ArtifactDraftControlProps = {
  'aria-describedby'?: string;
  'aria-invalid'?: true;
  'aria-required'?: true;
  id: string;
  required?: true;
};

type Props = {
  children: (props: ArtifactDraftControlProps) => ReactNode;
  className?: string;
  error?: string;
  hint?: string;
  hideLabel?: boolean;
  id?: string;
  label: ReactNode;
  required?: boolean;
};

export function ArtifactDraftField({ children, className = '', error, hideLabel = false, hint, id, label, required = false }: Props) {
  const generatedId = useId().replace(/:/g, '');
  const controlId = id ?? `artifact-draft-${generatedId}`;
  const hintId = hint ? `${controlId}-hint` : undefined;
  const errorId = error ? `${controlId}-error` : undefined;
  const describedBy = [hintId, errorId].filter(Boolean).join(' ') || undefined;

  return (
    <label className={`artifact-draft-field${error ? ' invalid' : ''}${className ? ` ${className}` : ''}`} htmlFor={controlId}>
      <span className={`artifact-draft-field-heading${hideLabel ? ' visually-hidden' : ''}`}>
        {label}
        {required ? <em>必填</em> : null}
      </span>
      {hint ? <small className="artifact-draft-field-hint" id={hintId}>{hint}</small> : null}
      {children({
        'aria-describedby': describedBy,
        'aria-invalid': error ? true : undefined,
        'aria-required': required ? true : undefined,
        id: controlId,
        required: required ? true : undefined,
      })}
      {error ? <small className="artifact-draft-field-error" id={errorId}>{error}</small> : null}
    </label>
  );
}
