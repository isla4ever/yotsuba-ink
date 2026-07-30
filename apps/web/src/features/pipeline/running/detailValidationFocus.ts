import type { DetailFieldErrors } from './detailDraftValidation';

export function focusFirstDetailError(errors: DetailFieldErrors) {
  const firstField = Object.keys(errors)[0];
  if (!firstField) return;
  window.requestAnimationFrame(() => {
    const target = Array.from(document.querySelectorAll<HTMLElement>('[data-detail-field]'))
      .find((element) => element.dataset.detailField === firstField);
    target?.focus();
  });
}

export function detailFieldErrorId(field: string) {
  return `detail-error-${field.replace(/[^a-zA-Z0-9_-]/g, '-')}`;
}
