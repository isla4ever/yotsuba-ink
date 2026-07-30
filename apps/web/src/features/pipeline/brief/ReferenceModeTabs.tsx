import { useRef, type KeyboardEvent, type ReactNode } from 'react';

export type ReferenceMode = 'smart_search' | 'url' | 'knowledge_base';

type ModeItem = {
  key: ReferenceMode;
  label: string;
  hint: string;
  icon: ReactNode;
};

type Props = {
  activeMode: ReferenceMode;
  idBase: string;
  items: ModeItem[];
  onChange: (mode: ReferenceMode) => void;
};

export function ReferenceModeTabs({ activeMode, idBase, items, onChange }: Props) {
  const refs = useRef<Array<HTMLButtonElement | null>>([]);

  const moveFocus = (event: KeyboardEvent<HTMLButtonElement>, index: number) => {
    let nextIndex = index;
    if (event.key === 'ArrowRight' || event.key === 'ArrowDown') nextIndex = (index + 1) % items.length;
    else if (event.key === 'ArrowLeft' || event.key === 'ArrowUp') nextIndex = (index - 1 + items.length) % items.length;
    else if (event.key === 'Home') nextIndex = 0;
    else if (event.key === 'End') nextIndex = items.length - 1;
    else return;
    event.preventDefault();
    onChange(items[nextIndex].key);
    refs.current[nextIndex]?.focus();
  };

  return (
    <div aria-label="参考资料方式" className="reference-mode-tabs" role="tablist">
      {items.map((item, index) => (
        <button
          aria-controls={`${idBase}-panel-${item.key}`}
          aria-selected={activeMode === item.key}
          className={activeMode === item.key ? 'active' : ''}
          id={`${idBase}-tab-${item.key}`}
          key={item.key}
          onClick={() => onChange(item.key)}
          onKeyDown={(event) => moveFocus(event, index)}
          ref={(element) => { refs.current[index] = element; }}
          role="tab"
          tabIndex={activeMode === item.key ? 0 : -1}
          type="button"
        >
          {item.icon}<strong>{item.label}</strong><small>{item.hint}</small>
        </button>
      ))}
    </div>
  );
}
