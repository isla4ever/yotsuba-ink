import { Globe2 } from 'lucide-react';
import { useMemo } from 'react';
import { bibleWorldView } from './storyBibleModel';
import type { RunEvent } from '../../contracts';

/** Read-only world canon: hard rules plus outline-stage anchor reveals, each labeled with its source stage. */
export function WorldSection({ events }: { events: RunEvent[] }) {
  const world = useMemo(() => bibleWorldView(events), [events]);
  if (!world.rules.length && !world.anchors.length) {
    return (
      <section className="bible-section bible-section-empty">
        <p className="bible-empty-note">世界观基线尚未建立——在创作立项阶段生成硬规则与锚点后，这里会展示全书设定清单。</p>
      </section>
    );
  }
  return (
    <section className="bible-section bible-world">
      <article className="bible-list-card">
        <h3><Globe2 size={15} />硬规则（{world.rules.length}）</h3>
        {world.rules.length ? (
          <ul className="bible-fact-list">
            {world.rules.map((rule, index) => (
              <li key={`${rule.text}-${index}`}>
                <span className="bible-fact-text">{rule.text}</span>
                <small className="bible-fact-source">{rule.source}</small>
              </li>
            ))}
          </ul>
        ) : (
          <p className="bible-empty-note">尚无已写回的硬规则。</p>
        )}
      </article>
      <article className="bible-list-card">
        <h3>世界揭示锚点（{world.anchors.length}）</h3>
        {world.anchors.length ? (
          <ul className="bible-fact-list">
            {world.anchors.map((anchor, index) => (
              <li key={`${anchor.anchor}-${index}`}>
                <span className="bible-fact-text">
                  {anchor.anchor ? <strong>{anchor.anchor}</strong> : null}
                  {anchor.reveal ? ` ${anchor.reveal}` : ''}
                  {anchor.rule ? `（规则：${anchor.rule}）` : ''}
                </span>
                <small className="bible-fact-source">{anchor.source}</small>
              </li>
            ))}
          </ul>
        ) : (
          <p className="bible-empty-note">分卷大纲尚未登记世界揭示。</p>
        )}
      </article>
    </section>
  );
}
