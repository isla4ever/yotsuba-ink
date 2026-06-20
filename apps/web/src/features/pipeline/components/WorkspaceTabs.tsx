import { Activity, BookOpenText, Clock3, KeyRound, Layers3, Library, Network, ScrollText, ShieldCheck } from 'lucide-react';
import type { WorkspaceKey } from '../types/workflow';

const tabs: Array<{ key: WorkspaceKey; label: string; icon: typeof Layers3; count?: string }> = [
  { key: 'pipeline', label: '流水线', icon: Layers3, count: '7' },
  { key: 'providers', label: 'Provider/API', icon: KeyRound, count: '3' },
  { key: 'prompts', label: 'Prompt 模板', icon: ScrollText, count: '6' },
  { key: 'wiki', label: 'Wiki/素材库', icon: Library, count: '12' },
  { key: 'characters', label: '人物关系网', icon: Network, count: '5' },
  { key: 'quality', label: '质量监控', icon: ShieldCheck, count: '实时' },
  { key: 'chapters', label: '正文进度', icon: BookOpenText, count: '3/6' },
  { key: 'history', label: '运行历史', icon: Clock3, count: '演示' },
];

type Props = {
  active: WorkspaceKey;
  onChange: (key: WorkspaceKey) => void;
};

export function WorkspaceTabs({ active, onChange }: Props) {
  return (
    <nav className="workspace-tabs" aria-label="工作区">
      {tabs.map((tab) => {
        const Icon = tab.icon;
        return (
          <button className={active === tab.key ? 'active' : ''} key={tab.key} onClick={() => onChange(tab.key)}>
            <Icon size={16} />
            <span>{tab.label}</span>
            <small>{tab.count}</small>
          </button>
        );
      })}
      <div className="sidebar-signal">
        <Activity size={15} />
        <span>Wiki 与质量门禁已转为横切运行层，不占用主链路节点。</span>
      </div>
    </nav>
  );
}
