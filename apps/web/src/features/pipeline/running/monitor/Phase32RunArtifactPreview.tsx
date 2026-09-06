import {
  AlertTriangle,
  CircleDashed,
  FileText,
  RefreshCw,
  ScanLine,
} from "lucide-react"
import type { Phase32CurrentArtifact } from "../../contracts/run"
import {
  projectMonitorArtifact,
  type MonitorDocumentBlock,
} from "../../lib/phase32RunMonitor"

type Props = {
  artifact: Phase32CurrentArtifact | null
  error: string
  loading: boolean
  onReload: () => void
  refreshing: boolean
  stageLabel: string
  unitRef: string
}

const BLOCK_LABELS: Record<string, string> = {
  action: "动作",
  dialogue: "对白",
  parenthetical: "括注",
  scene_heading: "场景",
  transition: "转场",
}

export function Phase32RunArtifactPreview({
  artifact,
  error,
  loading,
  onReload,
  refreshing,
  stageLabel,
  unitRef,
}: Props) {
  if (loading && !artifact) {
    return (
      <div className="phase32-monitor-content-state" role="status">
        <RefreshCw size={18} className="animate-spin text-action" />
        <strong>正在读取{stageLabel}内容</strong>
        <p>从当前 Run 的 Artifact Store 获取真实内容。</p>
      </div>
    )
  }

  if (error && !artifact) {
    return (
      <div className="phase32-monitor-content-state is-error" role="alert">
        <AlertTriangle size={18} />
        <strong>阶段内容读取失败</strong>
        <p>{error}</p>
        <button className="btn btn-secondary" onClick={onReload} type="button">
          <RefreshCw size={13} /> 重新读取
        </button>
      </div>
    )
  }

  if (!artifact) {
    return (
      <div className="phase32-monitor-content-state">
        <CircleDashed size={18} />
        <strong>{unitRef ? "该单元尚无正式内容" : "该阶段尚无正式内容"}</strong>
        <p>候选或提交 Artifact 生成后会在这里无感刷新，不显示模拟正文。</p>
      </div>
    )
  }

  const projection = projectMonitorArtifact(artifact)
  return (
    <article className="phase32-monitor-artifact page-in">
      <header className="phase32-monitor-artifact-heading">
        <div>
          <span>{projection.eyebrow}</span>
          <h2>{projection.title}</h2>
          <code>{unitRef || "aggregate"}</code>
        </div>
        <div className="phase32-monitor-artifact-state">
          {refreshing ? (
            <RefreshCw size={11} className="animate-spin" />
          ) : (
            <ScanLine size={11} />
          )}
          <span>
            {refreshing
              ? "正在同步最新版本"
              : artifact.status === "committed"
                ? "正式版本"
                : "候选版本"}
          </span>
        </div>
      </header>

      {error ? (
        <div className="phase32-monitor-stale-warning" role="status">
          <AlertTriangle size={12} />
          最新同步失败，当前保留上一次成功读取的内容。
          <button onClick={onReload} type="button">
            重试
          </button>
        </div>
      ) : null}

      {projection.fields.length ? (
        <dl className="phase32-monitor-field-grid">
          {projection.fields.map((field, index) => (
            <div
              className={field.wide ? "is-wide" : ""}
              key={`${field.label}-${index}`}
            >
              <dt>{field.label}</dt>
              <dd>{field.value}</dd>
            </div>
          ))}
        </dl>
      ) : null}

      {projection.document ? (
        <MonitorDocument document={projection.document} />
      ) : null}

      {projection.collections.map((collection) => (
        <section className="phase32-monitor-collection" key={collection.title}>
          <header>
            <span>{collection.title}</span>
            <strong>{collection.items.length}</strong>
          </header>
          <div>
            {collection.items.map((item, index) => (
              <article key={`${item.meta}-${index}`}>
                <header>
                  <span>{String(index + 1).padStart(2, "0")}</span>
                  <div>
                    <h3>{item.title}</h3>
                    {item.meta ? <code>{item.meta}</code> : null}
                  </div>
                </header>
                {item.fields.length ? (
                  <dl>
                    {item.fields.map((field, fieldIndex) => (
                      <div
                        className={field.wide ? "is-wide" : ""}
                        key={`${field.label}-${fieldIndex}`}
                      >
                        <dt>{field.label}</dt>
                        <dd>{field.value}</dd>
                      </div>
                    ))}
                  </dl>
                ) : null}
              </article>
            ))}
          </div>
        </section>
      ))}

      <footer className="phase32-monitor-artifact-receipt">
        <FileText size={12} />
        <span>{artifact.artifact_kind}</span>
        <code title={artifact.artifact_ref}>
          {shortRef(artifact.artifact_ref)}
        </code>
        <code title={artifact.payload_digest}>
          {shortDigest(artifact.payload_digest)}
        </code>
      </footer>
    </article>
  )
}

function MonitorDocument({
  document,
}: {
  document: {
    blocks: MonitorDocumentBlock[]
    paragraphs: string[]
    title: string
  }
}) {
  return (
    <section className="phase32-monitor-document">
      <header>
        <FileText size={13} />
        <span>{document.title}</span>
      </header>
      {document.blocks.length ? (
        <div className="phase32-monitor-screenplay">
          {document.blocks.map((block, index) => (
            <div className={`is-${block.kind}`} key={`${block.kind}-${index}`}>
              <small>{BLOCK_LABELS[block.kind] ?? block.kind}</small>
              {block.speaker ? <strong>{block.speaker}</strong> : null}
              <p>{block.text}</p>
            </div>
          ))}
        </div>
      ) : (
        <div className="phase32-monitor-manuscript">
          {document.paragraphs.map((paragraph, index) => (
            <p key={`${index}-${paragraph.slice(0, 24)}`}>{paragraph}</p>
          ))}
        </div>
      )}
    </section>
  )
}

function shortRef(value: string) {
  return value.length > 36 ? `${value.slice(0, 18)}…${value.slice(-10)}` : value
}

function shortDigest(value: string) {
  return value ? `${value.slice(0, 9)}…${value.slice(-7)}` : "-"
}
