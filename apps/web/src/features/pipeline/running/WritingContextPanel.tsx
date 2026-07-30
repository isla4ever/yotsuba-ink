import { BookOpenCheck, Flag, ShieldCheck, UserRoundCog } from 'lucide-react';
import type { WritingChapter } from './writingArtifactModel';
import {
  chapterKindLabel,
  chapterOutlinePresentation,
  previousChapterContext,
  trustedCharacterStates,
  trustedContextRules,
  trustedForeshadowLines,
  type DetailChapterContext,
} from './writingContextPresentation';

type Props = {
  chapter: WritingChapter;
  detailChapter?: DetailChapterContext;
  trustedCharacterNames: string[];
  readOnly: boolean;
  onSummaryChange: (summary: string) => void;
};

export function WritingContextPanel({
  chapter,
  detailChapter,
  trustedCharacterNames,
  readOnly,
  onSummaryChange,
}: Props) {
  const context = chapter.context_packet;
  const characterStates = trustedCharacterStates(context?.character_state, trustedCharacterNames);
  const rules = trustedContextRules(context);
  const foreshadows = trustedForeshadowLines(context);
  return (
    <section className="writing-context-panel">
      <div className="writing-rail-heading">
        <span>本章上下文</span>
        <small>{chapterKindLabel(context, Boolean(detailChapter))}</small>
      </div>
      <div className="writing-context-scroll">
        <ContextSection icon={BookOpenCheck} title="章节目标">
          <p>{chapterOutlinePresentation(context, detailChapter)}</p>
        </ContextSection>
        <ContextSection icon={Flag} title="前章承接">
          <p>{previousChapterContext(context)}</p>
        </ContextSection>
        <ContextSection icon={ShieldCheck} title="硬规则与伏笔">
          <ul>
            {rules.map((rule) => <li key={rule}>{rule}</li>)}
            {foreshadows.map((item) => <li key={item}>{item}</li>)}
            {!rules.length && !foreshadows.length ? <li>当前运行缺少可信规则与伏笔摘要。</li> : null}
          </ul>
        </ContextSection>
        <ContextSection icon={UserRoundCog} title="人物状态">
          <ul>
            {characterStates.map((item) => <li key={item.name}><strong>{item.name}：</strong>{item.status}</li>)}
            {!characterStates.length ? <li>当前运行缺少可信人物状态。</li> : null}
          </ul>
        </ContextSection>
        <label className={`writing-summary-field${chapter.summary_dirty ? ' needs-sync' : ''}`}>
          <span>{chapter.summary_dirty ? '章节摘要待同步' : '章节摘要'}</span>
          <textarea
            onChange={(event) => onSummaryChange(event.target.value)}
            readOnly={readOnly}
            rows={4}
            value={chapter.summary}
          />
        </label>
      </div>
    </section>
  );
}

function ContextSection({ icon: Icon, title, children }: { icon: typeof BookOpenCheck; title: string; children: React.ReactNode }) {
  return (
    <section className="writing-context-section">
      <h3><Icon aria-hidden="true" size={13} />{title}</h3>
      {children}
    </section>
  );
}
