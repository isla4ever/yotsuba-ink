import { Archive } from 'lucide-react';
import { templates } from '../data/defaultWorkflow';
import type { WorkspaceKey } from '../types/workflow';
import { WorkspaceTabs } from './WorkspaceTabs';

type Props = {
  active: WorkspaceKey;
  onChange: (key: WorkspaceKey) => void;
};

export function Sidebar({ active, onChange }: Props) {
  return (
    <aside className="app-sidebar">
      <div className="brand-block">
        <div className="brand-mark">NW</div>
        <div>
          <p>Novel Workflow</p>
          <strong>小说流水线平台</strong>
        </div>
      </div>
      <WorkspaceTabs active={active} onChange={onChange} />
      <section className="template-block">
        <div className="section-title"><Archive size={15} />流水线模板</div>
        {templates.map((item, index) => (
          <button className={index === 0 ? 'template active' : 'template'} key={item}>{item}</button>
        ))}
      </section>
    </aside>
  );
}
