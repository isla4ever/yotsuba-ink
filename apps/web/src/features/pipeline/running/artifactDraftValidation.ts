export type RequiredDraftField = {
  key: string;
  label: string;
  value: string | null | undefined;
};

export type DraftFieldErrors = Record<string, string>;

export function requiredDraftFieldErrors(fields: RequiredDraftField[]): DraftFieldErrors {
  return fields.reduce<DraftFieldErrors>((errors, field) => {
    if (!String(field.value ?? '').trim()) errors[field.key] = `请填写${field.label}`;
    return errors;
  }, {});
}

export function duplicateTrimmedValueIndexes(values: string[]) {
  const indexesByValue = new Map<string, number[]>();
  values.forEach((value, index) => {
    const normalized = value.trim();
    if (!normalized) return;
    indexesByValue.set(normalized, [...(indexesByValue.get(normalized) ?? []), index]);
  });
  return new Set(
    [...indexesByValue.values()]
      .filter((indexes) => indexes.length > 1)
      .flat(),
  );
}

export function draftErrorCount(...groups: DraftFieldErrors[]) {
  return groups.reduce((count, group) => count + Object.keys(group).length, 0);
}

export function normalizedDraftLines(value: string) {
  return value.split('\n').map((item) => item.trim()).filter(Boolean);
}
