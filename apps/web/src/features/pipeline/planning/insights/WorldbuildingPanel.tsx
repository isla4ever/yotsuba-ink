import { Edit3, Globe2 } from 'lucide-react';
import type { RunEvent } from '../../contracts';
import { extractWorldbuilding, type WorldbuildingView } from '../../lib/stageConfig';

type Props = {
  events: RunEvent[];
  artifactStatus?: 'draft' | 'confirmed';
  worldbuilding?: WorldbuildingView;
  onEdit?: () => void;
  stageEnrichment?: { label: string; detail: string };
};

export function WorldbuildingPanel({ artifactStatus, events, onEdit, stageEnrichment, worldbuilding }: Props) {
  const world = worldbuilding ?? extractWorldbuilding(events);
  const hasWorld = Boolean(world.seed || world.rules.length || world.tone || world.impact.length);
  return (
    <section className="worldbuilding-panel">
      <div className="worldbuilding-head">
        <div>
          <p className="eyebrow">设定资产</p>
          <h3><Globe2 size={15} />世界观</h3>
        </div>
        <div className="insight-head-actions">
          <span>{artifactStatus === 'draft' ? '当前稿预览' : artifactStatus === 'confirmed' ? '已定稿' : world.source}</span>
          {onEdit ? (
            <button aria-label="编辑世界观" className="insight-edit-button" onClick={onEdit} title="编辑世界观" type="button">
              <Edit3 size={14} />
            </button>
          ) : null}
        </div>
      </div>
      {stageEnrichment ? (
        <div className="insight-stage-enrichment world">
          <strong>{stageEnrichment.label}</strong>
          <span>{stageEnrichment.detail}</span>
        </div>
      ) : null}
      {hasWorld ? <p className="world-seed">{world.seed}</p> : <div className="runtime-widget-empty">等待创作立项生成世界规则。</div>}
      {hasWorld ? <div className="worldbuilding-grid">
        <article>
          <strong>硬设定</strong>
          {world.rules.slice(0, 3).map((item) => <span key={item}>{item}</span>)}
        </article>
        <article>
          <strong>风格基调</strong>
          <span>{world.tone}</span>
        </article>
        <article>
          <strong>后续影响</strong>
          {world.impact.slice(0, 3).map((item) => <span key={item}>{item}</span>)}
        </article>
      </div> : null}
    </section>
  );
}
