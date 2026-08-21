import * as Popover from '@radix-ui/react-popover';
import { BookOpen, Check, Database, Settings2, SlidersHorizontal } from 'lucide-react';
import type { CollaborationContextPolicy } from "../../contracts/authorCollaboration"
import type { KnowledgeDocument } from "../../contracts/knowledge"

type ContextOption =
  | 'include_author_preferences'
  | 'include_craft_mechanisms'
  | 'include_knowledge'
  | 'include_canon_wiki'
  | 'include_foreshadow';

type Props = {
  disabled: boolean;
  knowledgeDocuments: KnowledgeDocument[];
  onKnowledgeToggle: (docId: string) => void;
  onOpenKnowledgeManager: () => void;
  onOptionChange: (key: ContextOption, value: boolean) => void;
  policy: CollaborationContextPolicy | null;
};

export function ContextSourcePicker({
  disabled,
  knowledgeDocuments,
  onKnowledgeToggle,
  onOpenKnowledgeManager,
  onOptionChange,
  policy,
}: Props) {
  const selectedCount = policy?.source_pack_refs.length ?? 0;
  return (
    <Popover.Root>
      <Popover.Trigger
        aria-label="选择本轮上下文"
        className="collaboration-context-picker-trigger"
        disabled={disabled || !policy}
        title="选择本轮上下文"
        type="button"
      >
        <SlidersHorizontal size={15} />
        {selectedCount ? <span>{selectedCount}</span> : null}
      </Popover.Trigger>
      <Popover.Portal>
        <Popover.Content
          align="end"
          aria-label="本轮上下文来源"
          className="collaboration-context-picker"
          collisionPadding={12}
          side="top"
          sideOffset={8}
        >
          <header>
            <div><Database size={15} /><strong>本轮上下文</strong></div>
            <small>{selectedCount ? `${selectedCount} 份知识库资料` : '未选择知识库资料'}</small>
          </header>
          {policy ? (
            <div className="collaboration-context-option-list">
              <ContextOptionRow checked={policy.include_canon_wiki} label="相关 Canon / Wiki" onChange={(value) => onOptionChange('include_canon_wiki', value)} />
              <ContextOptionRow checked={policy.include_foreshadow} label="当前范围伏笔" onChange={(value) => onOptionChange('include_foreshadow', value)} />
              <ContextOptionRow checked={policy.include_author_preferences} label="作者偏好" onChange={(value) => onOptionChange('include_author_preferences', value)} />
              <ContextOptionRow checked={policy.include_craft_mechanisms} label="写作机制" onChange={(value) => onOptionChange('include_craft_mechanisms', value)} />
              <ContextOptionRow checked={policy.include_knowledge} label="本书知识库" onChange={(value) => onOptionChange('include_knowledge', value)} />
            </div>
          ) : null}
          <section className="collaboration-source-pack-list">
            <header><span><BookOpen size={13} />Source Pack</span><button onClick={onOpenKnowledgeManager} type="button"><Settings2 size={13} />管理</button></header>
            <div>
              {knowledgeDocuments.length ? knowledgeDocuments.map((document) => {
                const selected = policy?.source_pack_refs.includes(document.doc_id) ?? false;
                const unavailable = document.status === 'failed';
                return (
                  <button
                    aria-pressed={selected}
                    className={selected ? 'selected' : ''}
                    disabled={disabled || unavailable}
                    key={document.doc_id}
                    onClick={() => onKnowledgeToggle(document.doc_id)}
                    type="button"
                  >
                    <span>{selected ? <Check size={12} /> : null}</span>
                    <strong>{document.title}</strong>
                    <small>{unavailable ? '索引不可用' : `${document.chunk_count} 个片段`}</small>
                  </button>
                );
              }) : <p>暂无知识库资料</p>}
            </div>
          </section>
        </Popover.Content>
      </Popover.Portal>
    </Popover.Root>
  );
}

function ContextOptionRow({ checked, label, onChange }: { checked: boolean; label: string; onChange: (checked: boolean) => void }) {
  return (
    <label>
      <input checked={checked} onChange={(event) => onChange(event.target.checked)} type="checkbox" />
      <span>{label}</span>
    </label>
  );
}
