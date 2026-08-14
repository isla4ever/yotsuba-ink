import { CheckCircle2, CircleDashed, FilePenLine, GitBranch } from 'lucide-react';
import { useEffect, useMemo, useState } from 'react';
import { parseChapterArtifact, type ChapterArtifactVnext } from './artifactsVnext';
import { VnextArtifactError } from './VnextArtifactError';

type Props = { onArtifactChange: (artifact: ChapterArtifactVnext) => void; readOnly: boolean; result: string };

export function ChapterStageViewVnext({ onArtifactChange, readOnly, result }: Props) {
  const parsed = useMemo(() => parseChapterArtifact(result), [result]);
  const [artifact, setArtifact] = useState<ChapterArtifactVnext | null>(parsed.artifact);
  useEffect(() => { if (parsed.artifact) setArtifact(parsed.artifact); }, [parsed.artifact]);
  if (!artifact) return <VnextArtifactError errors={parsed.errors} label="Chapter Artifact" />;
  const update = (next: ChapterArtifactVnext) => { setArtifact(next); onArtifactChange(next); };
  const characterCount = Array.from(artifact.content).length;
  return (
    <div className="vnext-artifact-workbench chapter-vnext">
      <div className="vnext-chapter-statusbar">
        <span>{artifact.chapter_id}</span><strong>{artifact.version_id}</strong><span>{characterCount.toLocaleString()} 字符</span>
        <span className={`author-status ${artifact.author_status}`}><AuthorStatusIcon status={artifact.author_status} />{authorStatusLabel(artifact.author_status)}</span>
      </div>
      {/* While the next chapter streams, the incoming payload is prose rather
          than a committed artifact; the chapter on screen is still valid, so a
          parse complaint about the stream would only alarm the author. */}
      <section className="vnext-artifact-section vnext-prose-editor">
        <header><div><span>章节定稿</span><strong><FilePenLine size={15} />正文</strong></div></header>
        <label className="vnext-field"><span>章名</span><input onChange={(event) => update({ ...artifact, title: event.target.value, author_status: 'edited' })} readOnly={readOnly} value={artifact.title} /></label>
        <textarea aria-label="章节正文" className="vnext-prose-textarea" onChange={(event) => update({ ...artifact, content: event.target.value, author_status: 'edited' })} readOnly={readOnly} value={artifact.content} />
      </section>
    </div>
  );
}

function AuthorStatusIcon({ status }: { status: ChapterArtifactVnext['author_status'] }) {
  if (status === 'accepted') return <CheckCircle2 size={14} />;
  if (status === 'edited') return <FilePenLine size={14} />;
  if (status === 'branched') return <GitBranch size={14} />;
  return <CircleDashed size={14} />;
}

function authorStatusLabel(status: ChapterArtifactVnext['author_status']) {
  if (status === 'accepted') return '已接受';
  if (status === 'edited') return '作者已编辑';
  if (status === 'branched') return '分支版本';
  return '候选稿';
}
