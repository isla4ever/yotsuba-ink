import { BookOpenCheck, Plus, Trash2 } from 'lucide-react';
import { useState } from 'react';
import { UnsavedDraftDialog } from '../layout/UnsavedDraftDialog';
import { draftsEqual, useUnsavedDraftGuard } from '../state/useUnsavedDraftGuard';
import {
  OutlineDependencyDialogFooter,
  OutlineDependencyDialogShell,
  type OutlineDependencyDialogProps,
  useOutlinePortalModeClass,
} from './OutlineDependencyDialogShell';
import type { OutlineForeshadow } from './stageArtifacts';
import { ArtifactDraftField } from './ArtifactDraftField';
import { draftErrorCount, duplicateTrimmedValueIndexes, requiredDraftFieldErrors } from './artifactDraftValidation';

type LedgerRow = OutlineForeshadow & { key: string };

export function OutlineForeshadowLedgerDialog({ onClose, onSave, readOnly = false, volume }: OutlineDependencyDialogProps) {
  const [initialRows] = useState<LedgerRow[]>(() => (
    volume.foreshadow_plan.length
      ? volume.foreshadow_plan.map((item, index) => ({ ...item, key: `saved-${index}-${item.name}` }))
      : [emptyRow('new-0')]
  ));
  const [rows, setRows] = useState<LedgerRow[]>(() => structuredClone(initialRows));
  const dirty = !draftsEqual(initialRows, rows);
  const modeClass = useOutlinePortalModeClass();
  const scopeLabel = '伏笔账本当前稿';
  const draftGuard = useUnsavedDraftGuard({ dirty, readOnly, scopeLabel });
  const requestClose = () => draftGuard.requestAction({ kind: 'close', scopeLabel }, onClose);
  const update = (key: string, patch: Partial<LedgerRow>) => setRows((current) => current.map((row) => row.key === key ? { ...row, ...patch } : row));
  const duplicateNameIndexes = duplicateTrimmedValueIndexes(rows.map((row) => row.name));
  const rowErrors = rows.map((row, index) => {
    const errors = requiredDraftFieldErrors([
      { key: 'name', label: '线索名称', value: row.name },
      { key: 'chapter_range', label: '章节范围', value: row.chapter_range },
      { key: 'status', label: '伏笔状态', value: row.status },
      { key: 'note', label: '写入说明', value: row.note },
    ]);
    if (duplicateNameIndexes.has(index)) errors.name = '同卷线索名称不能重复';
    return errors;
  });
  const invalidCount = rowErrors.reduce((count, errors) => count + draftErrorCount(errors), 0) + (rows.length ? 0 : 1);

  return (
    <>
    <OutlineDependencyDialogShell icon={<BookOpenCheck size={18} />} kicker="伏笔规划" modeClass={modeClass} onClose={requestClose} readOnly={readOnly} suspended={Boolean(draftGuard.intent)} title="伏笔账本">
      <div className="outline-ledger-shell">
        <header><span>线索</span><span>章节</span><span>状态</span><span>写入说明</span><span /></header>
        <div className="outline-ledger-rows">
          {rows.map((row, index) => {
            const errors = rowErrors[index] ?? {};
            const rowPrefix = `outline-foreshadow-${index}`;
            return (
            <article key={row.key}>
              <ArtifactDraftField className="outline-ledger-field" error={errors.name} hideLabel id={`${rowPrefix}-name`} label="线索名称" required>
                {(controlProps) => <input {...controlProps} readOnly={readOnly} value={row.name} onChange={(event) => update(row.key, { name: event.target.value })} />}
              </ArtifactDraftField>
              <ArtifactDraftField className="outline-ledger-field" error={errors.chapter_range} hideLabel id={`${rowPrefix}-chapter`} label={`${row.name || '未命名线索'} 章节`} required>
                {(controlProps) => <input {...controlProps} readOnly={readOnly} value={row.chapter_range} onChange={(event) => update(row.key, { chapter_range: event.target.value })} />}
              </ArtifactDraftField>
              <ArtifactDraftField className="outline-ledger-field" error={errors.status} hideLabel id={`${rowPrefix}-status`} label={`${row.name || '未命名线索'} 状态`} required>
                {(controlProps) => (
                  <select {...controlProps} disabled={readOnly} value={row.status} onChange={(event) => update(row.key, { status: event.target.value as OutlineForeshadow['status'] })}>
                    <option>投放</option><option>推进</option><option>回收</option><option>延后</option>
                  </select>
                )}
              </ArtifactDraftField>
              <ArtifactDraftField className="outline-ledger-field" error={errors.note} hideLabel id={`${rowPrefix}-note`} label={`${row.name || '未命名线索'} 写入说明`} required>
                {(controlProps) => <textarea {...controlProps} readOnly={readOnly} value={row.note} onChange={(event) => update(row.key, { note: event.target.value })} />}
              </ArtifactDraftField>
              {readOnly || rows.length === 1 ? null : <button aria-label={`删除${row.name || '伏笔条目'}`} className="icon-button" onClick={() => setRows((current) => current.filter((item) => item.key !== row.key))} type="button"><Trash2 size={14} /></button>}
            </article>
            );
          })}
        </div>
        {readOnly ? null : <button className="ghost tiny-action" onClick={() => setRows((current) => [...current, emptyRow(`new-${current.length}-${Date.now()}`)])} type="button"><Plus size={14} />新增伏笔</button>}
      </div>
      <OutlineDependencyDialogFooter
        dirty={dirty}
        invalidCount={invalidCount}
        label="保存到当前稿"
        onClose={requestClose}
        onSave={() => onSave({
          foreshadow_plan: rows.map(({ key: _key, ...row }) => ({
            ...row,
            chapter_range: row.chapter_range.trim(),
            name: row.name.trim(),
            note: row.note.trim(),
          })),
        })}
        readOnly={readOnly}
      />
    </OutlineDependencyDialogShell>
    {draftGuard.intent ? <UnsavedDraftDialog intent={draftGuard.intent} modeClass={modeClass} onCancel={draftGuard.cancelDiscard} onDiscard={draftGuard.confirmDiscard} /> : null}
    </>
  );
}

function emptyRow(key: string): LedgerRow {
  return { key, name: '', status: '投放', chapter_range: '', note: '' };
}
