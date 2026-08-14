import { Plus, X } from 'lucide-react';

type Props = {
  label: string;
  onChange: (palette: string[]) => void;
  readOnly: boolean;
  values: string[];
};

const HEX_PATTERN = /^#(?:[0-9a-fA-F]{3}|[0-9a-fA-F]{6})$/;

/** Cover palette editor: visual swatches bound to the palette[] contract field. */
export function PaletteSwatchField({ label, onChange, readOnly, values }: Props) {
  const updateAt = (index: number, value: string) => {
    onChange(values.map((item, itemIndex) => itemIndex === index ? value : item));
  };
  return (
    <div className="vnext-palette-field">
      <span>{label}</span>
      <div className="vnext-palette-swatches">
        {values.map((value, index) => (
          <div className="vnext-palette-swatch" key={`${index}-${values.length}`}>
            <span
              aria-hidden="true"
              className="vnext-palette-dot"
              style={HEX_PATTERN.test(value.trim()) ? { background: value.trim() } : undefined}
            />
            {readOnly ? (
              <code>{value}</code>
            ) : (
              <input
                aria-label={`${label} ${index + 1}`}
                onChange={(event) => updateAt(index, event.target.value)}
                spellCheck={false}
                value={value}
              />
            )}
            {!readOnly && values.length > 1 ? (
              <button
                aria-label={`删除色值 ${value}`}
                onClick={() => onChange(values.filter((_, itemIndex) => itemIndex !== index))}
                type="button"
              >
                <X size={13} />
              </button>
            ) : null}
          </div>
        ))}
        {!readOnly && values.length < 8 ? (
          <button className="vnext-palette-add" onClick={() => onChange([...values, '#888888'])} type="button">
            <Plus size={13} />加色
          </button>
        ) : null}
      </div>
    </div>
  );
}
