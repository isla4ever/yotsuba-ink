import { Moon, Sun } from 'lucide-react';

type Props = {
  theme: 'dark' | 'light';
  onToggle: () => void;
};

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
      <span aria-hidden="true" className="theme-mode-switch-track">
        <span className="theme-mode-switch-thumb">{light ? <Sun size={13} /> : <Moon size={13} />}</span>
      </span>
    </button>
  );
}
