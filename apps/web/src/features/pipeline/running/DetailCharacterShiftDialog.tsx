import { Users } from 'lucide-react';
import { useMemo, useState } from 'react';
import { draftsEqual, useUnsavedDraftGuard } from '../state/useUnsavedDraftGuard';
import { validateDetailCharacterShiftDraft } from './detailDraftValidation';
import { focusFirstDetailError } from './detailValidationFocus';
import { CharacterShiftFields } from './DetailWritebackFields';
import {
  DetailWritebackDialogShell,
  type DetailWritebackDialogBaseProps,
} from './DetailWritebackDialogShell';
import type { DetailCharacterShift } from './stageArtifacts';

type Props = DetailWritebackDialogBaseProps & {
  onSave: (chapterIndex: number, value: DetailCharacterShift) => void;
};

export function DetailCharacterShiftDialog({ baseline, chapter, chapterIndex, chapters, onChapterChange, onClose, onSave, readOnly = false }: Props) {
  const [initialDraft] = useState(() => structuredClone(chapter.character_shift));
  const [draft, setDraft] = useState(() => structuredClone(initialDraft));
  const [validationAttempted, setValidationAttempted] = useState(false);
  const validation = useMemo(() => validateDetailCharacterShiftDraft(draft, baseline), [baseline, draft]);
  const dirty = !draftsEqual(initialDraft, draft);
  const scopeLabel = '人物变化当前稿';
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
      icon={<Users size={18} />}
      kicker="人物变化"
      onChapterChange={onChapterChange}
      onClose={onClose}
      onSave={save}
      readOnly={readOnly}
      scopeLabel={scopeLabel}
      title="人物变化"
      validationErrorCount={validationAttempted ? Object.keys(validation.errors).length : 0}
    >
      <CharacterShiftFields baseline={baseline} errors={validationAttempted ? validation.errors : {}} value={draft} onChange={setDraft} readOnly={readOnly} />
    </DetailWritebackDialogShell>
  );
}
