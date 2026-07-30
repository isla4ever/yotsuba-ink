import { BookOpenText, CircleAlert } from 'lucide-react';
import { motion } from 'motion/react';
import type { ReactNode } from 'react';
import { contentSwapMotionVariants } from '../lib/motion';
import type { DetailBaseline } from './detailArtifactModel';
import type { DetailBlueprintDraft, DetailFieldErrors } from './detailDraftValidation';
import { detailFieldErrorId } from './detailValidationFocus';

export type ChapterBlueprintValues = DetailBlueprintDraft;

type Props = {
  baseline: DetailBaseline;
  errors: DetailFieldErrors;
  onChange: (key: keyof ChapterBlueprintValues, value: string) => void;
  readOnly: boolean;
  validationAttempted: boolean;
  values: ChapterBlueprintValues;
};

export function ChapterBlueprintPaper({ baseline, errors, onChange, readOnly, validationAttempted, values }: Props) {
  return (
    <motion.section
      animate="animate"
      aria-label="章节蓝图编辑稿纸"
      className="chapter-blueprint-paper"
      exit="exit"
      initial="initial"
      variants={contentSwapMotionVariants}
    >
      {validationAttempted && Object.keys(errors).length ? (
        <div className="detail-validation-summary" role="alert"><CircleAlert size={15} />还有 {Object.keys(errors).length} 处内容需要补齐或修正</div>
      ) : null}
      <div className="chapter-paper-topline">
        <Field error={errors.chapter} field="chapter" label="章节名称"><input {...validationProps('chapter', errors.chapter)} readOnly={readOnly} value={values.chapter} onChange={(event) => onChange('chapter', event.target.value)} /></Field>
        <Field error={errors.pov} field="pov" label="视角人物"><select {...validationProps('pov', errors.pov)} disabled={readOnly} value={values.pov} onChange={(event) => onChange('pov', event.target.value)}><option value="">请选择已确认人物</option>{baseline.characters.map((item) => <option key={item.name} value={item.name}>{item.name}</option>)}</select></Field>
        <Field error={errors.scene} field="scene" label="主要场景"><input {...validationProps('scene', errors.scene)} readOnly={readOnly} value={values.scene} onChange={(event) => onChange('scene', event.target.value)} /></Field>
      </div>
      <div className="chapter-paper-grid">
        <TextField error={errors.entry_state} field="entry_state" icon label="场景进入状态" readOnly={readOnly} value={values.entry_state} onChange={(value) => onChange('entry_state', value)} />
        <TextField error={errors.goal} field="goal" label="章节行动目标" readOnly={readOnly} value={values.goal} onChange={(value) => onChange('goal', value)} />
        <TextField error={errors.conflict} field="conflict" label="核心冲突" readOnly={readOnly} value={values.conflict} onChange={(value) => onChange('conflict', value)} />
        <TextField error={errors.stakes} field="stakes" label="失败代价" readOnly={readOnly} value={values.stakes} onChange={(value) => onChange('stakes', value)} />
        <TextField error={errors.hook} field="hook" label="章末钩子" readOnly={readOnly} value={values.hook} onChange={(value) => onChange('hook', value)} />
        <TextField error={errors.continuity_notes} field="continuity_notes" label="正文交接与连续性" readOnly={readOnly} value={values.continuity_notes} onChange={(value) => onChange('continuity_notes', value)} />
      </div>
    </motion.section>
  );
}

function Field({ children, error, field, label }: { children: ReactNode; error?: string; field: string; label: string }) {
  return <label className={error ? 'detail-field-invalid' : ''}><span>{label}</span>{children}<FieldError error={error} field={field} /></label>;
}

function TextField({ error, field, icon, label, onChange, readOnly, value }: { error?: string; field: string; icon?: boolean; label: string; onChange: (value: string) => void; readOnly: boolean; value: string }) {
  return <label className={`chapter-paper-block${error ? ' detail-field-invalid' : ''}`}><span>{icon ? <BookOpenText size={14} /> : null}{label}</span><textarea {...validationProps(field, error)} readOnly={readOnly} value={value} onChange={(event) => onChange(event.target.value)} /><FieldError error={error} field={field} /></label>;
}

function FieldError({ error, field }: { error?: string; field: string }) {
  return error ? <small className="detail-field-error" id={detailFieldErrorId(field)}>{error}</small> : null;
}

function validationProps(field: string, error?: string) {
  return {
    'aria-describedby': error ? detailFieldErrorId(field) : undefined,
    'aria-invalid': Boolean(error),
    'data-detail-field': field,
  };
}
