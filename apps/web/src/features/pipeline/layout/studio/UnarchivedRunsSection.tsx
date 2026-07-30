import { Archive, ChevronDown, ExternalLink } from 'lucide-react';
import { useState } from 'react';
import type { RunHistoryItem } from '../../contracts';
import { LoadingButton } from '../LoadingButton';
import { formatWordCount, relativeTimeLabel, runStatusLabel } from './studioModel';

type Props = {
  runs: RunHistoryItem[];
  onOpenRun: (item: RunHistoryItem) => Promise<string>;
  onArchive: (item: RunHistoryItem) => Promise<unknown>;
};

/**
 * Legacy runs (project_id == run_id) shown as a collapsed group under the card
 * wall. Archiving creates a real Project record; the historical run itself is
 * kept unchanged — no fake migration.
 */
export function UnarchivedRunsSection({ runs, onOpenRun, onArchive }: Props) {
  const [expanded, setExpanded] = useState(false);
  const [pendingAction, setPendingAction] = useState('');
  if (runs.length === 0) return null;

  const runAction = async (id: string, kind: 'archive' | 'open', action: () => Promise<unknown>) => {
    setPendingAction(`${kind}:${id}`);
    try {
      await action();
    } finally {
      setPendingAction('');
    }
  };

  return (
    <section aria-labelledby="studio-unarchived-heading" className="studio-unarchived">
      <button
        aria-controls="studio-unarchived-list"
        aria-expanded={expanded}
        className="studio-unarchived-toggle"
        onClick={() => setExpanded((current) => !current)}
        type="button"
      >
        <ChevronDown aria-hidden="true" className={expanded ? 'open' : ''} size={16} />
        <span id="studio-unarchived-heading">未归档运行（{runs.length}）</span>
        <em>Studio 之前的历史运行；归档后历史运行仍按原记录保存。</em>
      </button>
      {expanded ? (
        <ul className="studio-unarchived-list" id="studio-unarchived-list">
          {runs.map((item) => (
            <li className="studio-unarchived-item" key={item.run_id}>
              <div className="studio-unarchived-info">
                <strong>{item.title}</strong>
                <span>
                  {runStatusLabel(item.status) || item.status} · {formatWordCount(item.words)} · {relativeTimeLabel(item.updated_at || item.created_at)}
                </span>
              </div>
              <div className="studio-unarchived-actions">
                <LoadingButton
                  className="ghost"
                  disabled={pendingAction.endsWith(`:${item.run_id}`)}
                  loading={pendingAction === `open:${item.run_id}`}
                  loadingLabel="打开中"
                  onClick={() => void runAction(item.run_id, 'open', () => onOpenRun(item))}
                  title="按原历史记录打开该运行"
                >
                  <ExternalLink aria-hidden="true" size={14} />打开
                </LoadingButton>
                <LoadingButton
                  className="ghost"
                  disabled={pendingAction.endsWith(`:${item.run_id}`)}
                  loading={pendingAction === `archive:${item.run_id}`}
                  loadingLabel="归档中"
                  onClick={() => void runAction(item.run_id, 'archive', () => onArchive(item))}
                  title="新建作品记录并关联该运行；历史运行仍按原记录保存"
                >
                  <Archive aria-hidden="true" size={14} />归档为作品
                </LoadingButton>
              </div>
            </li>
          ))}
        </ul>
      ) : null}
    </section>
  );
}
