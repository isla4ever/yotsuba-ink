import type {
  NovelBriefDraft,
  Phase32BriefDraft,
  ScreenplayBriefDraft,
} from "../lib/phase32Brief"
import { splitBriefRules } from "../lib/phase32Brief"

type Props = {
  artifact: Phase32BriefDraft
  editable: boolean
  onChange: (value: Record<string, unknown>) => void
}

export function Phase32BriefArtifactForm({
  artifact,
  editable,
  onChange,
}: Props) {
  return artifact.kind === "screenplay" ? (
    <ScreenplayForm
      artifact={artifact.value}
      editable={editable}
      onChange={onChange}
    />
  ) : (
    <NovelForm
      artifact={artifact.value}
      editable={editable}
      onChange={onChange}
    />
  )
}

function ScreenplayForm({
  artifact,
  editable,
  onChange,
}: Omit<Props, "artifact"> & { artifact: ScreenplayBriefDraft }) {
  const patch = (value: Partial<ScreenplayBriefDraft>) =>
    onChange({ ...artifact, ...value })
  return (
    <>
      <section className="phase32-brief-section is-primary">
        <SectionHeading label="样片定位" detail="可拍摄、可演示、可继续改编" />
        <TextField
          label="正式片名"
          value={artifact.title}
          editable={editable}
          onChange={(value) => patch({ title: value })}
        />
        <div className="phase32-brief-pair">
          <TextField
            label="样片类型"
            value={artifact.sample_type}
            editable={editable}
            onChange={(value) => patch({ sample_type: value })}
          />
          <TextField
            label="视听语气"
            value={artifact.tone}
            editable={editable}
            onChange={(value) => patch({ tone: value })}
          />
        </div>
        <TextArea
          label="故事前提"
          value={artifact.premise}
          editable={editable}
          onChange={(value) => patch({ premise: value })}
          prominent
        />
      </section>
      <section className="phase32-brief-section">
        <SectionHeading
          label="戏剧承诺"
          detail="冲突与结尾必须能在屏幕上被看见"
        />
        <TextArea
          label="观众承诺"
          value={artifact.audience_promise}
          editable={editable}
          onChange={(value) => patch({ audience_promise: value })}
        />
        <div className="phase32-brief-pair">
          <TextArea
            label="台面冲突"
            value={artifact.visible_conflict}
            editable={editable}
            onChange={(value) => patch({ visible_conflict: value })}
          />
          <TextArea
            label="结尾效果"
            value={artifact.ending_effect}
            editable={editable}
            onChange={(value) => patch({ ending_effect: value })}
          />
        </div>
      </section>
    </>
  )
}

function NovelForm({
  artifact,
  editable,
  onChange,
}: Omit<Props, "artifact"> & { artifact: NovelBriefDraft }) {
  const patch = (value: Partial<NovelBriefDraft>) =>
    onChange({ ...artifact, ...value })
  return (
    <>
      <section className="phase32-brief-section is-primary">
        <SectionHeading label="作品核心" detail="下游规划只引用确认后的版本" />
        <TextField
          label="正式书名"
          value={artifact.title}
          editable={editable}
          onChange={(value) => patch({ title: value })}
        />
        <TextArea
          label="故事前提"
          value={artifact.premise}
          editable={editable}
          onChange={(value) => patch({ premise: value })}
          prominent
        />
        <div className="phase32-brief-pair">
          <TextArea
            label="读者承诺"
            value={artifact.audience_promise}
            editable={editable}
            onChange={(value) => patch({ audience_promise: value })}
          />
          <TextArea
            label="主题问题"
            value={artifact.theme_question}
            editable={editable}
            onChange={(value) => patch({ theme_question: value })}
          />
        </div>
      </section>
      <section className="phase32-brief-section">
        <SectionHeading
          label="世界与收束"
          detail={`${artifact.world_rules.length} 条持续规则`}
        />
        <TextArea
          label="最少必要世界规则"
          value={artifact.world_rules.join("\n")}
          editable={editable}
          onChange={(value) => patch({ world_rules: splitBriefRules(value) })}
          rows={Math.max(3, artifact.world_rules.length)}
        />
        <div className="phase32-brief-pair">
          <TextArea
            label="结局方向"
            value={artifact.ending_direction}
            editable={editable}
            onChange={(value) => patch({ ending_direction: value })}
          />
          <TextArea
            label="叙事声音"
            value={artifact.narrative_voice}
            editable={editable}
            onChange={(value) => patch({ narrative_voice: value })}
          />
        </div>
      </section>
    </>
  )
}

type SectionHeadingProps = {
  label: string
  detail: string
}

function SectionHeading({ label, detail }: SectionHeadingProps) {
  return (
    <header className="phase32-brief-section-head">
      <h2>{label}</h2>
      <span>{detail}</span>
    </header>
  )
}

function TextField({
  label,
  value,
  editable,
  onChange,
}: {
  label: string
  value: string
  editable: boolean
  onChange: (value: string) => void
}) {
  if (!editable) {
    return (
      <div className="phase32-brief-field artifact-readable-field">
        <span>{label}</span>
        <p className="artifact-readable-value">{value}</p>
      </div>
    )
  }
  return (
    <label className="phase32-brief-field">
      <span>{label}</span>
      <input
        className="input"
        value={value}
        readOnly={!editable}
        onChange={(event) => onChange(event.target.value)}
      />
    </label>
  )
}

function TextArea({
  label,
  value,
  editable,
  onChange,
  prominent = false,
  rows = 4,
}: {
  label: string
  value: string
  editable: boolean
  onChange: (value: string) => void
  prominent?: boolean
  rows?: number
}) {
  if (!editable) {
    return (
      <div
        className={`phase32-brief-field artifact-readable-field${
          prominent ? " is-prominent is-emphasized" : ""
        }`}
      >
        <span>{label}</span>
        <p className="artifact-readable-value">{value}</p>
      </div>
    )
  }
  return (
    <label className={`phase32-brief-field${prominent ? " is-prominent" : ""}`}>
      <span>{label}</span>
      <textarea
        className="input"
        rows={rows}
        value={value}
        readOnly={!editable}
        onChange={(event) => onChange(event.target.value)}
      />
    </label>
  )
}
