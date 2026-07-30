import { FileCheck2 } from 'lucide-react';
import type { ExportFormat, ExportMetadata } from '../contracts';
import type { ExportArtifact } from './stageArtifacts';

type Chapter = NonNullable<ExportArtifact['chapters']>[number];

export function ExportSelectionPanel({
  chapters,
  format,
  formats,
  locked,
  metadata,
  onFormatChange,
  onMetadataChange,
  onSelectAll,
  onToggleChapter,
  selected,
}: {
  chapters: Chapter[];
  format: ExportFormat;
  formats: ExportFormat[];
  locked: boolean;
  metadata: ExportMetadata;
  onFormatChange: (format: ExportFormat) => void;
  onMetadataChange: (metadata: ExportMetadata) => void;
  onSelectAll: () => void;
  onToggleChapter: (id: string) => void;
  selected: string[];
}) {
  const allSelected = chapters.length > 0 && selected.length === chapters.length;
  const updateMetadata = (key: keyof ExportMetadata, value: string) => onMetadataChange({ ...metadata, [key]: value });

  return (
    <section aria-busy={locked} className="export-manifest-surface" data-locked={locked || undefined}>
      <div className="export-section-head">
        <div><p className="eyebrow">交付范围</p><h3><FileCheck2 size={15} />交付选择</h3></div>
        <button className="export-inline-action" disabled={locked} onClick={onSelectAll} type="button">{allSelected ? '清空' : '全选'}</button>
      </div>
      <div className="export-chapter-ledger" aria-label="导出章节">
        {chapters.map((chapter, index) => (
          <button aria-pressed={selected.includes(chapter.id)} className={selected.includes(chapter.id) ? 'selected' : ''} disabled={locked} key={chapter.id} onClick={() => onToggleChapter(chapter.id)} type="button">
            <span>{String(index + 1).padStart(2, '0')}</span>
            <strong>{chapter.title}</strong>
            <small>{chapter.words ? `${chapter.words.toLocaleString()} 字` : chapter.status ?? '就绪'}</small>
            <i>{selected.includes(chapter.id) ? '已选' : '待选'}</i>
          </button>
        ))}
      </div>
      <div className="export-format-fieldset" aria-label="导出格式选择">
        <span>导出格式</span>
        <div className="export-format-options" role="radiogroup" aria-label="导出格式">
          {formats.map((item) => (
            <button aria-checked={format === item} className={format === item ? 'active' : ''} disabled={locked} key={item} onClick={() => onFormatChange(item)} role="radio" type="button">
              {formatLabel(item)}
            </button>
          ))}
        </div>
      </div>
      <div className="export-metadata-grid">
        <label><span>作品标题</span><input disabled={locked} maxLength={200} value={metadata.title} onChange={(event) => updateMetadata('title', event.target.value)} /></label>
        <label><span>作者</span><input disabled={locked} maxLength={160} placeholder="可选" value={metadata.author} onChange={(event) => updateMetadata('author', event.target.value)} /></label>
        <label><span>交付包名称</span><input disabled={locked} maxLength={160} value={metadata.bundle_name} onChange={(event) => updateMetadata('bundle_name', event.target.value)} /></label>
        <label><span>版本说明</span><input disabled={locked} maxLength={500} placeholder="例如：编辑定稿版" value={metadata.version_note} onChange={(event) => updateMetadata('version_note', event.target.value)} /></label>
      </div>
    </section>
  );
}

function formatLabel(format: ExportFormat) {
  if (format === 'md') return 'Markdown';
  if (format === 'json') return 'JSON';
  return 'ZIP';
}
