import { Combobox } from '@base-ui/react/combobox';
import * as Select from '@radix-ui/react-select';
import { AlertTriangle, Check, ChevronDown, Search } from 'lucide-react';
import { useEffect, useId, useMemo, useRef, useState, type KeyboardEvent, type ReactNode } from 'react';
import {
  groupOptionItems,
  prepareOptionItems,
  shouldSearchOptions,
  type OptionFieldGroup,
  type OptionFieldItem,
} from './optionFieldModel';

type Props = {
  className?: string;
  description?: ReactNode;
  disabled?: boolean;
  emptyLabel?: string;
  error?: string;
  forceSearchable?: boolean;
  label: ReactNode;
  options: OptionFieldItem[];
  placeholder?: string;
  readOnly?: boolean;
  searchPlaceholder?: string;
  status?: 'ready' | 'warning' | 'disabled';
  statusText?: string;
  value: string;
  onValueChange: (value: string) => void;
};

export function OptionField({
  className = '', description, disabled = false, emptyLabel = '没有匹配的选项', error,
  forceSearchable = false, label, options, placeholder = '请选择', readOnly = false,
  searchPlaceholder = '搜索选项', status, statusText, value, onValueChange,
}: Props) {
  const labelId = useId();
  const messageId = useId();
  const items = useMemo(() => prepareOptionItems(options, value), [options, value]);
  const groups = useMemo(() => groupOptionItems(items), [items]);
  const searchable = shouldSearchOptions(items, forceSearchable);
  const effectiveDisabled = disabled || items.length === 0;
  const effectiveStatus = effectiveDisabled ? 'disabled' : status;
  return (
    <div
      className={`option-field ${className}`.trim()}
      data-readonly={readOnly || undefined}
      data-status={effectiveStatus}
    >
      <span className="option-field-label" id={labelId}>{label}</span>
      {description ? <span className="option-field-description">{description}</span> : null}
      {searchable ? (
        <SearchableOptionControl
          disabled={effectiveDisabled}
          emptyLabel={emptyLabel}
          groups={groups}
          describedBy={error || statusText ? messageId : undefined}
          labelId={labelId}
          placeholder={placeholder}
          readOnly={readOnly}
          searchPlaceholder={searchPlaceholder}
          value={value}
          onValueChange={onValueChange}
        />
      ) : (
        <CompactOptionControl
          disabled={effectiveDisabled}
          groups={groups}
          describedBy={error || statusText ? messageId : undefined}
          labelId={labelId}
          placeholder={placeholder}
          readOnly={readOnly}
          value={value}
          onValueChange={onValueChange}
        />
      )}
      {error ? <span className="option-field-message is-error" id={messageId} role="alert"><AlertTriangle size={12} />{error}</span> : null}
      {!error && statusText ? <span className="option-field-message" id={messageId}>{statusText}</span> : null}
    </div>
  );
}

type ControlProps = {
  describedBy?: string;
  disabled: boolean;
  groups: OptionFieldGroup[];
  labelId: string;
  placeholder: string;
  readOnly: boolean;
  value: string;
  onValueChange: (value: string) => void;
};

function CompactOptionControl({ describedBy, disabled, groups, labelId, placeholder, readOnly, value, onValueChange }: ControlProps) {
  const [open, setOpen] = useState(false);
  return (
    <Select.Root
      disabled={disabled}
      open={open}
      value={value}
      onOpenChange={(nextOpen) => setOpen(readOnly ? false : nextOpen)}
      onValueChange={(nextValue) => { if (!readOnly) onValueChange(nextValue); }}
    >
      <Select.Trigger
        aria-labelledby={labelId}
        aria-describedby={describedBy}
        aria-readonly={readOnly}
        className="option-field-trigger"
        data-readonly={readOnly || undefined}
        onPointerDown={(event) => { if (readOnly) event.preventDefault(); }}
      >
        <Select.Value placeholder={placeholder} />
        <Select.Icon><ChevronDown size={15} /></Select.Icon>
      </Select.Trigger>
      <Select.Portal>
        <Select.Content align="start" className="option-field-popup option-field-select-popup" collisionPadding={12} position="popper" sideOffset={5}>
          <Select.Viewport className="option-field-list">
            {groups.map((group) => (
              <Select.Group key={group.value}>
                {group.label ? <Select.Label className="option-field-group-label">{group.label}</Select.Label> : null}
                {group.items.map((item) => (
                  <Select.Item className="option-field-item" disabled={item.disabled} key={item.value} value={item.value}>
                    <span className="option-field-indicator-slot">
                      <Select.ItemIndicator className="option-field-indicator"><Check size={14} /></Select.ItemIndicator>
                    </span>
                    <Select.ItemText>{item.label}</Select.ItemText>
                    {item.meta ? <span className="option-field-item-meta">{item.meta}</span> : null}
                  </Select.Item>
                ))}
              </Select.Group>
            ))}
          </Select.Viewport>
        </Select.Content>
      </Select.Portal>
    </Select.Root>
  );
}

function SearchableOptionControl({
  describedBy, disabled, emptyLabel, groups, labelId, placeholder, readOnly, searchPlaceholder, value, onValueChange,
}: ControlProps & { emptyLabel: string; searchPlaceholder: string }) {
  const [open, setOpen] = useState(false);
  const [inputValue, setInputValue] = useState('');
  const [portalContainer, setPortalContainer] = useState<HTMLElement | null>(null);
  const composingRef = useRef(false);
  const inputRef = useRef<HTMLInputElement>(null);
  const selected = groups.flatMap((group) => group.items).find((item) => item.value === value) ?? null;
  useEffect(() => {
    if (typeof document !== 'undefined') setPortalContainer(document.querySelector<HTMLElement>('.provider-manager-sheet'));
  }, []);
  useEffect(() => {
    if (!open) return;
    const frame = window.requestAnimationFrame(() => inputRef.current?.focus());
    return () => window.cancelAnimationFrame(frame);
  }, [open]);
  const handleInputKeyDown = (event: KeyboardEvent<HTMLInputElement>) => {
    if (event.key === 'Escape') {
      event.preventDefault();
      event.stopPropagation();
      if (inputValue) setInputValue('');
      else setOpen(false);
      return;
    }
    if ((event.nativeEvent.isComposing || composingRef.current) && event.key === 'Enter') {
      event.stopPropagation();
    }
  };
  const handlePopupKeyDown = (event: KeyboardEvent<HTMLDivElement>) => {
    if (event.key !== 'Escape') return;
    event.preventDefault();
    event.stopPropagation();
    if (inputValue) setInputValue('');
    else setOpen(false);
  };
  return (
    <Combobox.Root
      disabled={disabled}
      inputValue={inputValue}
      isItemEqualToValue={(item, selectedItem) => item.value === selectedItem.value}
      itemToStringLabel={(item) => item.label}
      items={groups}
      open={open}
      readOnly={readOnly}
      value={selected}
      onInputValueChange={setInputValue}
      onOpenChange={(nextOpen) => {
        if (readOnly) return;
        setOpen(nextOpen);
        if (nextOpen) setInputValue('');
      }}
      onValueChange={(item) => {
        if (item && !readOnly) onValueChange(item.value);
      }}
    >
      <Combobox.Trigger aria-describedby={describedBy} aria-labelledby={labelId} className="option-field-trigger" data-readonly={readOnly || undefined}>
        <Combobox.Value placeholder={placeholder} />
        <Combobox.Icon><ChevronDown size={15} /></Combobox.Icon>
      </Combobox.Trigger>
      <Combobox.Portal container={portalContainer ?? undefined}>
        <Combobox.Backdrop className="option-field-backdrop" />
        <Combobox.Positioner align="start" className="option-field-positioner" collisionPadding={12} sideOffset={5}>
          <Combobox.Popup
            aria-label={searchPlaceholder}
            className="option-field-popup option-field-combobox-popup"
            initialFocus={inputRef}
            onKeyDownCapture={handlePopupKeyDown}
          >
            <div className="option-field-search-row">
              <Search aria-hidden size={15} />
              <Combobox.Input
                aria-label={searchPlaceholder}
                autoComplete="off"
                className="option-field-search-input"
                placeholder={searchPlaceholder}
                ref={inputRef}
                onCompositionEnd={() => { composingRef.current = false; }}
                onCompositionStart={() => { composingRef.current = true; }}
                onKeyDownCapture={handleInputKeyDown}
              />
            </div>
            <Combobox.Empty className="option-field-empty">{emptyLabel}</Combobox.Empty>
            <Combobox.List className="option-field-list">
              {(group: OptionFieldGroup) => (
                <Combobox.Group className="option-field-group" items={group.items} key={group.value}>
                  {group.label ? <Combobox.GroupLabel className="option-field-group-label">{group.label}</Combobox.GroupLabel> : null}
                  <Combobox.Collection>
                    {(item: OptionFieldItem) => (
                      <Combobox.Item className="option-field-item" disabled={item.disabled} key={item.value} value={item}>
                        <Combobox.ItemIndicator className="option-field-indicator" keepMounted><Check size={14} /></Combobox.ItemIndicator>
                        <span className="option-field-item-copy">
                          <strong>{item.label}</strong>
                          {item.description ? <small>{item.description}</small> : null}
                        </span>
                        {item.meta ? <span className="option-field-item-meta">{item.meta}</span> : null}
                      </Combobox.Item>
                    )}
                  </Combobox.Collection>
                </Combobox.Group>
              )}
            </Combobox.List>
          </Combobox.Popup>
        </Combobox.Positioner>
      </Combobox.Portal>
    </Combobox.Root>
  );
}
