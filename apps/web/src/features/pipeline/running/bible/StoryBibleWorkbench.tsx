import '../../../../styles/entry-bible.css';
import { BookMarked } from 'lucide-react';
import { CharactersSection } from './CharactersSection';
import { FactsSection } from './FactsSection';
import { ForeshadowSection } from './ForeshadowSection';
import { WorldSection } from './WorldSection';
import { bibleSectionMeta, bibleSections, type BibleSection } from '../../lib/stageRoutes';
import { useRunEvents, useUICommandContext, useWorkflowConfigContext } from '../../state/pipelineShellContext';

type Props = {
  section: BibleSection;
};

/**
 * Story Bible page: read-only browsing over the run's continuity systems
 * (characters, world canon, foreshadow ledger, canon facts). Editing stays in
 * each stage's finalize flow — this page never writes back and never touches
 * providers, resume, or SSE.
 */
export function StoryBibleWorkbench({ section }: Props) {
  // Content surface: full run-events subscription (Phase 12 F5 store).
  const { events } = useRunEvents();
  const { workflow } = useWorkflowConfigContext();
  const ui = useUICommandContext();
  const meta = bibleSectionMeta[section];

  return (
    <section aria-label="Story Bible 工作台" className="workbench story-bible-workbench">
      <header className="bible-head">
        <div>
          <p className="eyebrow"><BookMarked size={13} />Story Bible · 只读</p>
          <h2>{meta.label}</h2>
          <p className="bible-head-note">此页只读浏览连续性事实；人物、设定、伏笔与事实的修改在对应阶段定稿时写回。</p>
        </div>
        <nav aria-label="Story Bible 分区" className="bible-section-nav">
          {bibleSections.map((item) => (
            <button
              aria-current={item === section ? 'page' : undefined}
              className={`bible-section-tab${item === section ? ' active' : ''}`}
              key={item}
              onClick={() => ui.navigateBible(item)}
              type="button"
            >
              {bibleSectionMeta[item].label}
            </button>
          ))}
        </nav>
      </header>
      {section === 'cast' ? <CharactersSection events={events} workflow={workflow} /> : null}
      {section === 'world' ? <WorldSection events={events} /> : null}
      {section === 'foreshadow' ? <ForeshadowSection events={events} /> : null}
      {section === 'facts' ? <FactsSection events={events} /> : null}
    </section>
  );
}
