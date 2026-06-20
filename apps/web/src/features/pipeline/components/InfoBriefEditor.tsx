import { useState } from 'react';
import type { InputField, WorkflowStage } from '../types/workflow';
import { addTagValue, coerceFieldValue, removeTagValue, updateStageInputDefault } from '../utils/stageConfig';
import { ReferenceResearchPanel } from './references/ReferenceResearchPanel';

type Props = {
  stage: WorkflowStage;
  onKnowledgeDocumentsChanged?: () => void;
  onOpenKnowledgeManager?: () => void;
  onChange: (stage: WorkflowStage) => void;
};

const briefFields = ['genre', 'target_length', 'target_words_range', 'audience', 'core_concept', 'keywords', 'taboos'];

export function InfoBriefEditor({ stage, onChange, onKnowledgeDocumentsChanged, onOpenKnowledgeManager }: Props) {
  const fields = briefFields.map((key) => stage.input_schema.find((field) => field.key === key)).filter(Boolean) as InputField[];
  return (
    <div className="info-brief-editor">
      <div className="brief-summary">
        <strong>先给系统最少但关键的创作 Brief</strong>
        <span>参考资料改为三选一，复杂检索、上传、RAG 摘要都收进参考模块，避免一开始给创作者太大压力。</span>
      </div>
      <div className="brief-field-grid">
        {fields.map((field) => (
          <BriefInput
            field={field}
            key={field.key}
            onChange={(value) => onChange(updateStageInputDefault(stage, field.key, value))}
          />
        ))}
      </div>
      <ReferenceResearchPanel
        stage={stage}
        onChange={onChange}
        onKnowledgeDocumentsChanged={onKnowledgeDocumentsChanged}
        onOpenKnowledgeManager={onOpenKnowledgeManager}
      />
    </div>
  );
}

function BriefInput({ field, onChange }: { field: InputField; onChange: (value: unknown) => void }) {
  const id = `brief-${field.key}`;
  return (
    <label className={field.type === 'textarea' ? 'stage-input-field wide brief-input' : 'stage-input-field brief-input'} htmlFor={id}>
      <span>{field.label}{field.required ? <b>必填</b> : null}</span>
      {field.type === 'select' ? (
        <select id={id} value={String(field.default ?? '')} onChange={(event) => onChange(event.target.value)}>
          {(field.options ?? []).map((option) => <option key={option} value={option}>{option}</option>)}
        </select>
      ) : null}
      {field.type === 'textarea' ? (
        <textarea id={id} className="stage-input-textarea" value={String(field.default ?? '')} onChange={(event) => onChange(event.target.value)} />
      ) : null}
      {field.type === 'tags' ? <TagInput field={field} onChange={onChange} /> : null}
      {field.type !== 'select' && field.type !== 'textarea' && field.type !== 'tags' ? (
        <input id={id} type={field.type === 'number' ? 'number' : 'text'} value={String(field.default ?? '')} onChange={(event) => onChange(coerceFieldValue(field, event.target.value))} />
      ) : null}
    </label>
  );
}

function TagInput({ field, onChange }: { field: InputField; onChange: (value: unknown) => void }) {
  const tags = Array.isArray(field.default) ? field.default.map(String) : [];
  const [draft, setDraft] = useState('');
  const commit = () => {
    if (!draft.trim()) return;
    onChange(addTagValue(field.default, draft));
    setDraft('');
  };
  return (
    <div className="tag-input-box">
      <div className="tag-chip-row">
        {tags.map((tag) => (
          <button type="button" key={tag} onClick={() => onChange(removeTagValue(field.default, tag))}>{tag}<span>×</span></button>
        ))}
      </div>
      <input
        value={draft}
        placeholder="输入后按回车添加"
        onChange={(event) => setDraft(event.target.value)}
        onKeyDown={(event) => {
          if (event.key === 'Enter' || event.key === ',' || event.key === '，' || event.key === '、') {
            event.preventDefault();
            commit();
          }
        }}
        onBlur={commit}
      />
    </div>
  );
}
