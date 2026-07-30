import { ChevronDown, Layers3 } from 'lucide-react';
import type { SidebarStageItem } from './workbenchSidebarModel';

type Props = {
  currentStageId: string;
  items: SidebarStageItem[];
  onNavigate: (stageId: string) => void;
};

export function HeaderStageSwitcher({ currentStageId, items, onNavigate }: Props) {
  return (
    <label className="header-stage-switcher">
      <Layers3 aria-hidden="true" size={14} />
      <span className="header-stage-switcher-label">切换创作阶段</span>
      <select
        aria-label="切换创作阶段"
        onChange={(event) => onNavigate(event.target.value)}
        value={currentStageId}
      >
        {items.map((item, index) => (
          <option disabled={item.disabled} key={item.id} value={item.id}>
            {String(index + 1).padStart(2, '0')} {item.label} · {item.statusLabel}
          </option>
        ))}
      </select>
      <ChevronDown aria-hidden="true" className="header-stage-switcher-chevron" size={13} />
    </label>
  );
}
