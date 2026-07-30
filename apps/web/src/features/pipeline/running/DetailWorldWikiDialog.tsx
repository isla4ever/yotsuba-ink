import { Globe2 } from 'lucide-react';
import { useMemo, useState } from 'react';
import { draftsEqual, useUnsavedDraftGuard } from '../state/useUnsavedDraftGuard';
import { validateDetailWorldWikiDraft, type DetailWorldWikiDraft } from './detailDraftValidation';
import { focusFirstDetailError } from './detailValidationFocus';
import { WorldWikiFields } from './DetailWritebackFields';
import {
  DetailWritebackDialogShell,
  type DetailWritebackDialogBaseProps,
} from './DetailWritebackDialogShell';
import { createDetailDraftRows, detailDraftValues } from './detailWritebackRows';

type Props = DetailWritebackDialogBaseProps & {
  onSave: (chapterIndex: number, value: DetailWorldWikiDraft) => void;
};

export function DetailWorldWikiDialog({ baseline, chapter, chapterIndex, chapters, onChapterChange, onClose, onSave, readOnly = false }: Props) {
  const [initialDraft] = useState(() => ({
    facts: createDetailDraftRows('fact', chapter.fact_reveals),
    wiki: createDetailDraftRows('wiki', chapter.wiki_candidates),
  }));
  const [draft, setDraft] = useState(() => structuredClone(initialDraft));
  const [validationAttempted, setValidationAttempted] = useState(false);
  const validation = useMemo(() => validateDetailWorldWikiDraft({
    fact_reveals: detailDraftValues(draft.facts),
    wiki_candidates: detailDraftValues(draft.wiki),
  }, baseline), [baseline, draft]);
  const dirty = !draftsEqual(initialDraft, draft);
  const scopeLabel = '事实与 Wiki 当前稿';
  const draftGuard = useUnsavedDraftGuard({ dirty, readOnly, scopeLabel });
  const save = () => {
    setValidationAttempted(true);
    if (!validation.valid) {
      focusFirstDetailError(validation.errors);
      return;
    }
    onSave(chapterIndex, validation.value);
  };

  return (
    <DetailWritebackDialogShell
      chapter={chapter}
      chapterIndex={chapterIndex}
      chapters={chapters}
      dirty={dirty}
      draftGuard={draftGuard}
      icon={<Globe2 size={18} />}
      kicker="事实与 Wiki"
      onChapterChange={onChapterChange}
      onClose={onClose}
      onSave={save}
      readOnly={readOnly}
      scopeLabel={scopeLabel}
      title="事实 / Wiki"
      validationErrorCount={validationAttempted ? Object.keys(validation.errors).length : 0}
    >
      <WorldWikiFields
        baseline={baseline}
        errors={validationAttempted ? validation.errors : {}}
        facts={draft.facts}
        onFactsChange={(facts) => setDraft((current) => ({ ...current, facts }))}
        wiki={draft.wiki}
        onWikiChange={(wiki) => setDraft((current) => ({ ...current, wiki }))}
        readOnly={readOnly}
      />
    </DetailWritebackDialogShell>
  );
}
