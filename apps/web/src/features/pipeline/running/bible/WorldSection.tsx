import { Globe2, Landmark, ScrollText } from 'lucide-react';
import { useMemo } from 'react';
import { bibleWorldView } from './storyBibleModel';
import type { RunEvent } from '../../contracts';

/** Read-only world canon: hard rules plus volume/detail anchor reveals, each labeled with its source stage. */
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
      <dl className="bible-summary-strip">
        <div><dt><ScrollText size={13} />硬规则</dt><dd>{world.rules.length}</dd></div>
        <div><dt><Landmark size={13} />世界揭示锚点</dt><dd>{world.anchors.length}</dd></div>
        <div className="bible-summary-note"><dt>约束语义</dt><dd>硬规则全书不可违反；锚点按分卷计划揭示</dd></div>
      </dl>
      <div className="bible-world-grid">
        <article className="bible-ledger-card">
          <header className="bible-ledger-card-head">
            <h3><Globe2 size={15} />硬规则</h3>
            <span>{world.rules.length ? `${world.rules.length} 条 · 全书生效` : '暂无'}</span>
          </header>
          {world.rules.length ? (
            <ol className="bible-rule-list">
              {world.rules.map((rule, index) => (
                <li key={`${rule.text}-${index}`}>
                  <span aria-hidden="true" className="bible-rule-index">{String(index + 1).padStart(2, '0')}</span>
                  <p className="bible-rule-text">{rule.text}</p>
                  <small className="bible-fact-source">{rule.source}</small>
                </li>
              ))}
            </ol>
          ) : (
            <p className="bible-empty-note">尚无已写回的硬规则。</p>
          )}
        </article>
        <article className="bible-ledger-card">
          <header className="bible-ledger-card-head">
            <h3><Landmark size={15} />世界揭示锚点</h3>
            <span>{world.anchors.length ? `${world.anchors.length} 处` : '待分卷登记'}</span>
          </header>
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
            <div className="bible-card-empty" role="status">
              <Landmark size={18} />
              <p>分卷架构尚未登记世界揭示。</p>
              <small>分卷定稿时，每卷的世界揭示计划会写回到这里。</small>
            </div>
          )}
        </article>
      </div>
    </section>
  );
}
