import { Fingerprint, GitBranch, ShieldCheck, Waypoints } from "lucide-react"
import type { CreationRouteId } from "../contracts/run"
import {
  castDiagnostics,
  castRoutePresentation,
  shortCastRef,
  type CharacterBibleDraft,
} from "../lib/phase32Cast"

export function CastInspector({
  artifact,
  artifactRef,
  revisionLabel,
  routeId,
  selectedSubjectRef,
}: {
  artifact: CharacterBibleDraft
  artifactRef: string
  revisionLabel: string
  routeId: CreationRouteId
  selectedSubjectRef: string
}) {
  const diagnostics = castDiagnostics(artifact)
  const copy = castRoutePresentation(routeId)
  const relationDegree =
    diagnostics.relationshipDegree.get(selectedSubjectRef) ?? 0

  return (
    <aside className="phase32-cast-inspector" aria-label="人物阶段检查器">
      <header>
        <span>STAGE INSPECTOR</span>
        <strong>人物合同</strong>
      </header>
      <section className="phase32-cast-inspector-stats">
        <div>
          <strong>{diagnostics.characterCount}</strong>
          <span>冻结人物</span>
        </div>
        <div>
          <strong>{diagnostics.relationshipCount}</strong>
          <span>有向关系</span>
        </div>
        <div>
          <strong>{relationDegree}</strong>
          <span>当前连接</span>
        </div>
      </section>
      <section className="phase32-cast-inspector-ledger">
        <div>
          <Fingerprint size={13} />
          <span>
            <strong>身份冻结</strong>
            <small>
              人物增删不在本轮草稿权限内；新关系只能引用已登记人物。
            </small>
          </span>
        </div>
        <div>
          <GitBranch size={13} />
          <span>
            <strong>投影边界</strong>
            <small>3D 坐标可随视图重建，不写回人物圣经。</small>
          </span>
        </div>
        <div>
          <Waypoints size={13} />
          <span>
            <strong>下游使用</strong>
            <small>{copy.nextUse}</small>
          </span>
        </div>
        <div>
          <ShieldCheck size={13} />
          <span>
            <strong>孤立人物</strong>
            <small>
              {diagnostics.isolatedSubjectRefs.length
                ? `${diagnostics.isolatedSubjectRefs.length} 人尚无正式关系，可作为审读提示。`
                : "全部人物至少进入一条正式关系。"}
            </small>
          </span>
        </div>
      </section>
      <footer>
        <span>{revisionLabel}</span>
        <code title={artifactRef}>{shortCastRef(artifactRef)}</code>
      </footer>
    </aside>
  )
}
