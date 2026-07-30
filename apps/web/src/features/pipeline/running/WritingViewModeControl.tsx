import { Focus, PenLine, ShieldCheck } from 'lucide-react';
import type { WritingViewMode } from './writingViewMode';

type Props = {
  mode: WritingViewMode;
  onChange: (mode: WritingViewMode) => void;
};

const options = [
  { id: 'writing', icon: PenLine, label: '写作' },
  { id: 'review', icon: ShieldCheck, label: '审校' },
  { id: 'focus', icon: Focus, label: '专注' },
] as const;

export function WritingViewModeControl({ mode, onChange }: Props) {
  return (
    <div aria-label="正文工作视图" className="writing-view-mode-control" role="group">
      {options.map(({ id, icon: Icon, label }) => (
        <button
          aria-pressed={mode === id}
          key={id}
          onClick={() => onChange(id)}
          type="button"
        >
          <Icon aria-hidden="true" size={13} />
          <span>{label}</span>
        </button>
      ))}
    </div>
  );
}
