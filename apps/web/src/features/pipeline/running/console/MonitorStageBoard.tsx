import type { StageType } from '../../contracts';
import type { MonitorSelection } from './MonitorSidebar';
import type { MonitorSnapshot } from './monitorModel';
import { monitorChapterStatusLabel, monitorStageStatusLabel } from './monitorModel';

type Props = {
  snapshot: MonitorSnapshot;
  selection: MonitorSelection;
  /** Content-reading tab: chapters render full prose instead of a tail preview. */
  reading?: boolean;
};

const PROSE_PREVIEW_CHARS = 1600;

/**
 * Read-only stage content for the monitor console: condensed by default,
 * full chapter prose when the console's 内容阅读 tab is active. Never the
 * full editing surface.
 */
export function MonitorStageBoard({ snapshot, selection, reading = false }: Props) {
  if (selection.kind === 'chapter') {
    return <ChapterBoard chapterRef={selection.chapterRef} full={reading} snapshot={snapshot} />;
  }
  const stage = snapshot.stages.find((entry) => entry.id === selection.stageId);
  const type: StageType = stage?.type ?? 'brief';
  return (
    <article className="monitor-board">
      <header className="monitor-board-head">
        <h2>{stage?.label ?? '阶段'}</h2>
        <span className={`monitor-board-status status-${stage?.status ?? 'idle'}`}>
          {monitorStageStatusLabel[stage?.status ?? 'idle']}
        </span>
      </header>
      {type === 'brief' ? <BriefBoard snapshot={snapshot} /> : null}
      {type === 'spine' ? <SpineBoard snapshot={snapshot} /> : null}
      {type === 'cast' ? <CastBoard snapshot={snapshot} /> : null}
      {type === 'volumes' ? <VolumesBoard snapshot={snapshot} /> : null}
      {type === 'detail' ? <DetailBoard snapshot={snapshot} /> : null}
      {type === 'text' ? <TextBoard full={reading} snapshot={snapshot} /> : null}
      {type === 'cover' ? <CoverBoard snapshot={snapshot} /> : null}
      {type === 'export' ? <ExportBoard snapshot={snapshot} /> : null}
    </article>
  );
}

function EmptyBoard({ hint }: { hint: string }) {
  return <p className="monitor-board-empty">{hint}</p>;
}

function BriefBoard({ snapshot }: { snapshot: MonitorSnapshot }) {
  const brief = snapshot.brief;
  if (!brief) return <EmptyBoard hint="创作契约生成后将在此展示书名、题材承诺与叙事口吻。" />;
  return (
    <div className="monitor-board-body">
      <dl className="monitor-fact-grid">
        <Fact label="书名" value={brief.title} wide />
        <Fact label="一句话前提" value={brief.premise} wide />
        <Fact label="题材承诺" value={brief.promise} wide />
        <Fact label="叙事口吻" value={brief.voice} wide />
        <Fact label="目标字数" value={brief.length_envelope.word_target_soft ? `${brief.length_envelope.word_target_soft.toLocaleString()} 字` : '未指定'} />
        <Fact label="目标章数" value={brief.length_envelope.chapter_target_soft ? `${brief.length_envelope.chapter_target_soft} 章` : '未指定'} />
        <Fact label="主题" value={brief.theme} />
        <Fact label="结局承诺" value={brief.ending_promise} />
      </dl>
    </div>
  );
}

function SpineBoard({ snapshot }: { snapshot: MonitorSnapshot }) {
  const spine = snapshot.spine;
  if (!spine) return <EmptyBoard hint="故事脊柱生成后将在此展示因果转折链。" />;
  return (
    <div className="monitor-board-body">
      <ol className="monitor-turn-list">
        {spine.turns.map((turn, position) => (
          <li key={turn.id}>
            <span className="monitor-turn-ordinal">{position + 1}</span>
            <span className="monitor-turn-copy">
              <strong>{turn.cause}</strong>
              <small>{turn.change}</small>
            </span>
          </li>
        ))}
      </ol>
      <p className="monitor-board-note">结局锚点：{spine.ending}</p>
    </div>
  );
}

function CastBoard({ snapshot }: { snapshot: MonitorSnapshot }) {
  const cast = snapshot.cast;
  if (!cast) return <EmptyBoard hint="人物圣经生成后将在此展示人物阵容。" />;
  return (
    <div className="monitor-board-body">
      <div className="monitor-cast-grid">
        {cast.subjects.map((subject) => (
          <div className={`monitor-cast-card kind-${subject.kind}`} key={subject.id}>
            <strong>{subject.name}</strong>
            <small>{castKindLabel[subject.kind] ?? subject.kind}</small>
            <p>{subject.function}</p>
          </div>
        ))}
      </div>
      <p className="monitor-board-note">{cast.relations.length} 条关系压力已登记</p>
    </div>
  );
}

function VolumesBoard({ snapshot }: { snapshot: MonitorSnapshot }) {
  const volumes = snapshot.volumes;
  if (!volumes) return <EmptyBoard hint="分卷架构生成后将在此展示每卷承诺与高潮。" />;
  return (
    <div className="monitor-board-body">
      <div className="monitor-volume-strip">
        {volumes.volumes.map((volume, position) => (
          <div className="monitor-volume-card" key={volume.id}>
            <header>
              <span>卷 {position + 1}</span>
              <small>{volume.turn_refs.length} 个转折 · {volume.cast_ids.length} 位人物</small>
            </header>
            <p className="monitor-volume-promise">{volume.promise}</p>
            <dl>
              <div><dt>冲突</dt><dd>{volume.conflict}</dd></div>
              <div><dt>高潮</dt><dd>{volume.climax}</dd></div>
              <div><dt>闭合</dt><dd>{volume.closure}</dd></div>
            </dl>
          </div>
        ))}
      </div>
    </div>
  );
}

function DetailBoard({ snapshot }: { snapshot: MonitorSnapshot }) {
  if (!snapshot.detail) return <EmptyBoard hint="章节施工图生成后将在此展示卷章结构。" />;
  return (
    <div className="monitor-board-body">
      {snapshot.tree.map((volume) => (
        <section className="monitor-detail-volume" key={volume.ref}>
          <header>卷 {volume.ordinal} · {volume.chapters.length} 章</header>
          <ul>
            {volume.chapters.map((chapter) => (
              <li key={chapter.ref}>
                <span className={`monitor-chip status-${chapter.status}`}>{monitorChapterStatusLabel[chapter.status]}</span>
                <strong>{chapter.title || chapter.purpose}</strong>
                <small>POV {chapter.pov} · {chapter.sceneCount} 场景</small>
              </li>
            ))}
          </ul>
        </section>
      ))}
    </div>
  );
}

function TextBoard({ full, snapshot }: { full?: boolean; snapshot: MonitorSnapshot }) {
  const activeChapter = snapshot.tree
    .flatMap((volume) => volume.chapters)
    .find((chapter) => chapter.status === 'writing' || chapter.status === 'reviewing');
  const written = snapshot.tree.flatMap((volume) => volume.chapters).filter((chapter) => chapter.words > 0);
  const focus = activeChapter ?? written[written.length - 1];
  if (!focus) return <EmptyBoard hint="正文生成开始后将在此实时预览章节文本。" />;
  return <ChapterBoard chapterRef={focus.ref} full={full} snapshot={snapshot} />;
}

function ChapterBoard({ chapterRef, full, snapshot }: { chapterRef: string; full?: boolean; snapshot: MonitorSnapshot }) {
  const chapter = snapshot.tree.flatMap((volume) => volume.chapters).find((entry) => entry.ref === chapterRef);
  const body = snapshot.chapterBodies.get(chapterRef);
  const content = body?.content ?? '';
  const preview = !full && content.length > PROSE_PREVIEW_CHARS ? `…${content.slice(-PROSE_PREVIEW_CHARS)}` : content;
  return (
    <article className="monitor-board">
      <header className="monitor-board-head">
        <h2>{chapter?.title || chapter?.purpose || chapterRef}</h2>
        <span className={`monitor-board-status status-${chapter?.status ?? 'pending'}`}>
          {monitorChapterStatusLabel[chapter?.status ?? 'pending']}
          {chapter?.words ? ` · ${chapter.words.toLocaleString()} 字` : ''}
        </span>
      </header>
      {chapter?.purpose ? <p className="monitor-board-note">本章目标：{chapter.purpose}</p> : null}
      {preview ? (
        <div className={`monitor-prose${body?.completed ? '' : ' streaming'}`}>{preview}</div>
      ) : (
        <EmptyBoard hint="该章节尚未开始生成正文。" />
      )}
    </article>
  );
}

function CoverBoard({ snapshot }: { snapshot: MonitorSnapshot }) {
  const cover = snapshot.cover;
  if (!cover) return <EmptyBoard hint="封面简报生成后将在此展示视觉概念与色板。" />;
  return (
    <div className="monitor-board-body">
      <dl className="monitor-fact-grid">
        <Fact label="视觉概念" value={cover.brief.concept} wide />
        <Fact label="生成指令" value={cover.brief.image_prompt} wide />
      </dl>
      <div className="monitor-palette-row">
        {cover.brief.palette.map((color) => (
          <span className="monitor-palette-chip" key={color} style={{ background: color }} title={color} />
        ))}
      </div>
      <p className="monitor-board-note">{cover.selected_asset_id ? '封面资产已选定' : '等待封面资产选定'}</p>
    </div>
  );
}

function ExportBoard({ snapshot }: { snapshot: MonitorSnapshot }) {
  const artifact = snapshot.exportArtifact;
  if (!artifact) return <EmptyBoard hint="导出交付包生成后将在此展示交付信息。" />;
  return (
    <div className="monitor-board-body">
      <dl className="monitor-fact-grid">
        <Fact label="书名" value={artifact.metadata.title} wide />
        <Fact label="导出格式" value={artifact.format.toUpperCase()} />
        <Fact label="章节数" value={`${artifact.chapter_version_ids.length} 章`} />
        <Fact label="封面资产" value={artifact.cover_asset_id ? '已包含' : '未包含'} />
        <Fact label="版本说明" value={artifact.metadata.version_note || '—'} />
      </dl>
    </div>
  );
}

function Fact({ label, value, wide }: { label: string; value: string; wide?: boolean }) {
  return (
    <div className={`monitor-fact${wide ? ' wide' : ''}`}>
      <dt>{label}</dt>
      <dd>{value || '—'}</dd>
    </div>
  );
}

const castKindLabel: Record<string, string> = {
  functional: '功能角色',
  historical_record: '史料人物',
  major: '主要角色',
  npc: '路人',
  protagonist: '主角',
};
