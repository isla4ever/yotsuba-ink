import type { WritingChapter } from './writingArtifactModel';
import type { DetailChapterContext } from './writingContextPresentation';
import { WritingChapterNav } from './WritingChapterNav';
import { WritingContextPanel } from './WritingContextPanel';
import { WritingRevisionHistory } from './WritingRevisionHistory';

type Props = {
  activeChapterId: string;
  chapters: WritingChapter[];
  detailChapter?: DetailChapterContext;
  locked: boolean;
  onOpenVersions: () => void;
  onSelectChapter: (chapterId: string) => void;
  onSummaryChange: (summary: string) => void;
  readOnly: boolean;
  revisionHistory: WritingChapter['revision_history'];
  selectedChapter: WritingChapter;
  trustedCharacterNames: string[];
  versionCount: number;
};

export function WritingChapterWorkspace({
  activeChapterId,
  chapters,
  detailChapter,
  locked,
  onOpenVersions,
  onSelectChapter,
  onSummaryChange,
  readOnly,
  revisionHistory,
  selectedChapter,
  trustedCharacterNames,
  versionCount,
}: Props) {
  return (
    <aside className="writing-workbench-rail">
      <WritingChapterNav
        activeChapterId={activeChapterId}
        chapters={chapters}
        locked={locked}
        onSelect={onSelectChapter}
      />
      <WritingContextPanel
        chapter={selectedChapter}
        detailChapter={detailChapter}
        onSummaryChange={onSummaryChange}
        readOnly={readOnly}
        trustedCharacterNames={trustedCharacterNames}
      />
      <WritingRevisionHistory
        onOpenVersions={onOpenVersions}
        revisions={revisionHistory}
        versionCount={versionCount}
      />
    </aside>
  );
}
