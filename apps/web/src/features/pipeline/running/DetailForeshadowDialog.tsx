import { GitBranch } from 'lucide-react';
import { useMemo, useState } from 'react';
import { draftsEqual, useUnsavedDraftGuard } from '../state/useUnsavedDraftGuard';
import { validateDetailForeshadowDraft } from './detailDraftValidation';
import { focusFirstDetailError } from './detailValidationFocus';
import { ForeshadowFields } from './DetailWritebackFields';
import {
  DetailWritebackDialogShell,
  type DetailWritebackDialogBaseProps,
} from './DetailWritebackDialogShell';
import { createDetailDraftRows, detailDraftValues } from './detailWritebackRows';
import type { DetailForeshadow } from './stageArtifacts';

type Props = DetailWritebackDialogBaseProps & {
  onSave: (chapterIndex: number, value: DetailForeshadow[]) => void;
};

export function DetailForeshadowDialog({ baseline, chapter, chapterIndex, chapters, onChapterChange, onClose, onSave, readOnly = false }: Props) {
  const [initialDraft] = useState(() => createDetailDraftRows('clue', chapter.foreshadow));
  const [draft, setDraft] = useState(() => structuredClone(initialDraft));
  const [validationAttempted, setValidationAttempted] = useState(false);
  const validation = useMemo(() => validateDetailForeshadowDraft(detailDraftValues(draft)), [draft]);
  const dirty = !draftsEqual(initialDraft, draft);
  const scopeLabel = '伏笔账本当前稿';
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
      icon={<GitBranch size={18} />}
      kicker="伏笔规划"
      onChapterChange={onChapterChange}
      onClose={onClose}
      onSave={save}
      readOnly={readOnly}
      scopeLabel={scopeLabel}
      title="伏笔账本"
      validationErrorCount={validationAttempted ? Object.keys(validation.errors).length : 0}
    >
      <ForeshadowFields baseline={baseline} errors={validationAttempted ? validation.errors : {}} value={draft} onChange={setDraft} readOnly={readOnly} />
    </DetailWritebackDialogShell>
  );
}
