export type OptionFieldItem = {
  value: string;
  label: string;
  description?: string;
  meta?: string;
  group?: string;
  disabled?: boolean;
};

export type OptionFieldGroup = {
  value: string;
  label?: string;
  items: OptionFieldItem[];
};

export function prepareOptionItems(items: OptionFieldItem[], currentValue: string) {
  const seen = new Set<string>();
  const unique = items.filter((item) => {
    if (!item.value || seen.has(item.value)) return false;
    seen.add(item.value);
    return true;
  });
  if (!currentValue || seen.has(currentValue)) return unique;
  return [...unique, { value: currentValue, label: currentValue, meta: '当前配置' }];
}

export function shouldSearchOptions(items: OptionFieldItem[], forceSearchable = false) {
  return forceSearchable || items.length > 7 || items.some((item) => Boolean(item.group || item.description));
}

export function groupOptionItems(items: OptionFieldItem[]): OptionFieldGroup[] {
  const hasNamedGroup = items.some((item) => Boolean(item.group));
  const groups = new Map<string, OptionFieldGroup>();
  items.forEach((item) => {
    const label = item.group || (hasNamedGroup ? '其他' : undefined);
    const key = label ?? '__ungrouped';
    const group = groups.get(key) ?? { value: key, label, items: [] };
    group.items.push(item);
    groups.set(key, group);
  });
  return Array.from(groups.values());
}
