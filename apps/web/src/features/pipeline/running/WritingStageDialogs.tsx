import { AnimatePresence } from 'motion/react';
import type { ComponentProps } from 'react';
import { ChapterRevisionPreview } from './ChapterRevisionPreview';
import { ChapterVersionHistory } from './ChapterVersionHistory';

type Props = {
  revision: ComponentProps<typeof ChapterRevisionPreview> | null;
  versionHistory: ComponentProps<typeof ChapterVersionHistory> | null;
};

export function WritingStageDialogs({ revision, versionHistory }: Props) {
  return (
    <AnimatePresence>
      {revision ? <ChapterRevisionPreview {...revision} key="chapter-revision-preview" /> : null}
      {versionHistory ? <ChapterVersionHistory {...versionHistory} key="chapter-version-history" /> : null}
    </AnimatePresence>
  );
}
