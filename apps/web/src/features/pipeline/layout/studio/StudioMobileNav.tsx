import { Clock3, Layers, Library, Plus } from 'lucide-react';
import { useLocation, useNavigate } from 'react-router-dom';
import { useUICommandContext } from '../../state/pipelineShellContext';

export function StudioMobileNav() {
  const ui = useUICommandContext();
  const location = useLocation();
  const navigate = useNavigate();
  const templateView = new URLSearchParams(location.search).get('view') === 'templates';
  return (
    <header className="studio-mobile-nav">
      <div className="studio-mobile-brand">
        <span aria-hidden="true" className="brand-mark">NW</span>
        <div><strong>Yotsuba Ink</strong><span>作品工作室</span></div>
      </div>
      <nav aria-label="工作室移动导航">
        <button aria-current={!templateView ? 'page' : undefined} aria-label="作品库" onClick={() => navigate('/studio')} title="作品库" type="button"><Library size={17} /></button>
        <button aria-current={templateView ? 'page' : undefined} aria-label="工作流模板" onClick={() => navigate('/studio?view=templates')} title="工作流模板" type="button"><Layers size={17} /></button>
        <button aria-label="创作历史" onClick={ui.openHistory} title="创作历史" type="button"><Clock3 size={17} /></button>
        <button aria-label="新建作品" className="studio-mobile-create" onClick={ui.requestNewProject} title="新建作品" type="button"><Plus size={18} /></button>
      </nav>
    </header>
  );
}
