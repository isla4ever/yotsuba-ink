import { CircleCheck, FilePenLine, History, TriangleAlert } from 'lucide-react';
import type { WritingRevision } from './writingArtifactModel';

type Props = {
  onOpenVersions: () => void;
  revisions: WritingRevision[];
  versionCount: number;
};

export function WritingRevisionHistory({ onOpenVersions, revisions, versionCount }: Props) {
  return (
    <section className="writing-revision-history">
      <div className="writing-rail-heading">
        <span>修订轨迹</span>
        <button aria-label={`查看章节版本（${versionCount} 个）`} onClick={onOpenVersions} title="查看章节版本" type="button"><History size={12} /><span>{versionCount}</span></button>
      </div>
      <div className="writing-revision-list">
        {revisions.length ? revisions.slice(-6).reverse().map((revision) => {
          const Icon = revision.status === 'blocking' ? TriangleAlert : revision.type === 'manual_edit' ? FilePenLine : CircleCheck;
          return (
            <article className={revision.status} key={revision.id}>
              <Icon aria-hidden="true" size={13} />
              <span><strong>{revision.label}</strong><small>{revision.detail}</small></span>
            </article>
          );
        }) : <p>本章尚无修订记录。</p>}
      </div>
    </section>
  );
}
