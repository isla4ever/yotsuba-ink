import { BookOpenText, Edit3, GitBranch, Globe2, Users } from 'lucide-react';
import type { ReactNode } from 'react';
import type { DetailChapter } from './detailPresentation';
import { detailClueSummary, detailFactSummary } from './detailPresentation';

type DetailWritebackEditor = 'wiki' | 'character' | 'foreshadow';

type Props = {
  chapter: DetailChapter | null;
  onEditBlueprint: () => void;
  onOpenWriteback: (editor: DetailWritebackEditor) => void;
  readOnly: boolean;
};

export function DetailChapterLedger({ chapter, onEditBlueprint, onOpenWriteback, readOnly }: Props) {
  return (
    <section aria-label="当前章节上下文账本" className="detail-chapter-ledger">
      <header>
        <div><p className="eyebrow">当前章上下文</p><h3>{chapter?.chapter || '等待章节'}</h3><span>{chapter ? `${chapter.pov || 'POV 待补齐'} / ${chapter.scene || '场景待补齐'}` : '选择章节后查看施工交接。'}</span></div>
        <button className="tiny-action detail-blueprint-action" disabled={!chapter} onClick={onEditBlueprint} type="button"><Edit3 size={13} />{readOnly ? '查看蓝图' : '编辑蓝图'}</button>
      </header>
      <div className="detail-chapter-ledger-lanes">
        <section><span><BookOpenText size={13} />正文交接</span><p>{chapter?.continuity_notes || '连续性说明待补齐'}</p></section>
        <LedgerButton disabled={!chapter} icon={<Globe2 size={13} />} label="事实 / Wiki" summary={chapter ? detailFactSummary(chapter) : ''} target="世界观与 Wiki" onClick={() => onOpenWriteback('wiki')} />
        <LedgerButton disabled={!chapter} icon={<Users size={13} />} label="人物变化" summary={chapter?.character_shift.change || ''} target="人物图谱" onClick={() => onOpenWriteback('character')} />
        <LedgerButton disabled={!chapter} icon={<GitBranch size={13} />} label="伏笔账本" summary={chapter ? detailClueSummary(chapter) : ''} target="开放线索" onClick={() => onOpenWriteback('foreshadow')} />
      </div>
    </section>
  );
}

function LedgerButton({ disabled, icon, label, onClick, summary, target }: { disabled: boolean; icon: ReactNode; label: string; onClick: () => void; summary: string; target: string }) {
  return (
    <button aria-label={`${label}，定稿后写回${target}`} disabled={disabled} onClick={onClick} type="button">
      <span>{icon}{label}<small>定稿后写回 {target}</small></span>
      <p>{summary || '待维护'}</p>
    </button>
  );
}
