import { Globe2 } from 'lucide-react';
import type { RunEvent } from '../../contracts';
import { extractWorldbuilding } from '../../lib/stageConfig';

type Props = {
  events: RunEvent[];
};

export function WorldbuildingPanel({ events }: Props) {
  const world = extractWorldbuilding(events);
  return (
    <section className="worldbuilding-panel">
      <div className="worldbuilding-head">
        <div>
          <p className="eyebrow">Worldbuilding</p>
          <h3><Globe2 size={15} />世界观</h3>
        </div>
        <span>{world.source}</span>
      </div>
      <p className="world-seed">{world.seed}</p>
      <div className="worldbuilding-grid">
        <article>
          <strong>硬设定</strong>
          {world.rules.slice(0, 3).map((item) => <span key={item}>{item}</span>)}
        </article>
        <article>
          <strong>风格基调</strong>
          <span>{world.tone}</span>
        </article>
        <article>
          <strong>链路影响</strong>
          {world.impact.slice(0, 3).map((item) => <span key={item}>{item}</span>)}
        </article>
      </div>
      {world.source === '默认草案' ? <small>运行小说推荐阶段后，世界观种子会自动更新并约束后续梗概、大纲和正文。</small> : null}
    </section>
  );
}
