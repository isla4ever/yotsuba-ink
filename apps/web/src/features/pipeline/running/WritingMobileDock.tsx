import { BookOpenText, ShieldCheck } from 'lucide-react';

type Props = {
  chapterLabel: string;
  onOpenChapter: () => void;
  onOpenReview: () => void;
  reviewLabel: string;
};

export function WritingMobileDock({ chapterLabel, onOpenChapter, onOpenReview, reviewLabel }: Props) {
  return (
    <nav aria-label="正文移动工作区" className="writing-mobile-dock">
      <button onClick={onOpenChapter} type="button">
        <BookOpenText aria-hidden="true" size={16} />
        <span><strong>当前章节</strong><small>{chapterLabel}</small></span>
      </button>
      <button onClick={onOpenReview} type="button">
        <ShieldCheck aria-hidden="true" size={16} />
        <span><strong>本章审校</strong><small>{reviewLabel}</small></span>
      </button>
    </nav>
  );
}
