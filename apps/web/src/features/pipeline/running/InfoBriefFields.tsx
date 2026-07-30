import type { InfoRecommendation } from './infoRecommendationModel';

type TitlePickerProps = {
  readOnly: boolean;
  recommendation: InfoRecommendation;
  onChange: (patch: Partial<InfoRecommendation>) => void;
};

export function InfoTitlePicker({ readOnly, recommendation, onChange }: TitlePickerProps) {
  return (
    <div className="recommendation-title-picker refined-title-picker">
      <span>书名候选</span>
      <div>
        {recommendation.title_candidates.map((title, index) => (
          <button className={title === recommendation.selected_title ? 'active' : ''} disabled={readOnly} key={`${title}-${index}`} onClick={() => onChange({ selected_title: title })} type="button">
            <i>{String(index + 1).padStart(2, '0')}</i>{title}
          </button>
        ))}
      </div>
      <label className="info-custom-title-field">
        <span>当前书名</span>
        <input aria-label="当前书名，可直接自定义" readOnly={readOnly} value={recommendation.selected_title} onChange={(event) => onChange({ selected_title: event.target.value })} />
      </label>
    </div>
  );
}

type TagEditorProps = {
  draft: string;
  readOnly: boolean;
  tags: string[];
  onAdd: (value: string) => void;
  onDraftChange: (value: string) => void;
  onRemove: (tag: string) => void;
};

export function InfoTagEditor({ draft, onAdd, onDraftChange, onRemove, readOnly, tags }: TagEditorProps) {
  return (
    <div className="recommendation-tag-console">
      <span>创作标签</span>
      <div className={`recommendation-chip-row editable${readOnly ? ' readonly' : ''}`}>
        {tags.map((tag, index) => (
          <button aria-label={readOnly ? `创作标签：${tag}` : `移除创作标签：${tag}`} className={`tone-${index % 3}`} disabled={readOnly} key={tag} onClick={() => onRemove(tag)} type="button">
            {tag}{readOnly ? null : <i aria-hidden="true">x</i>}
          </button>
        ))}
        {readOnly ? null : (
          <input
            aria-label="新增创作标签，按回车录入"
            disabled={tags.length >= 8}
            onChange={(event) => onDraftChange(event.target.value)}
            onKeyDown={(event) => {
              if (event.key !== 'Enter') return;
              event.preventDefault();
              onAdd(draft);
            }}
            placeholder={tags.length >= 8 ? '标签已满' : '回车添加'}
            value={draft}
          />
        )}
      </div>
    </div>
  );
}
