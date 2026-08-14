import { Moon, Sun } from 'lucide-react';

type Props = {
  theme: 'dark' | 'light';
  onToggle: () => void;
};

/** The button itself is the track — no wrapper frame around the pill. */
export function ThemeModeSwitch({ theme, onToggle }: Props) {
  const light = theme === 'light';
  const label = light ? '切换夜间模式' : '切换日间模式';
  return (
    <button
      aria-checked={light}
      aria-label={label}
      className={`theme-mode-switch ${light ? 'light' : 'dark'}`}
      onClick={onToggle}
      role="switch"
      type="button"
    >
      <span aria-hidden="true" className="theme-mode-switch-glyph is-moon"><Moon size={12} /></span>
      <span aria-hidden="true" className="theme-mode-switch-glyph is-sun"><Sun size={12} /></span>
      <span aria-hidden="true" className="theme-mode-switch-thumb" />
    </button>
  );
}
