import { Database, RotateCcw, ShieldCheck, SlidersHorizontal } from 'lucide-react';
import type { WorkflowDefinition } from '../types/workflow';

type Props = {
  kind: 'wiki' | 'quality';
  workflow: WorkflowDefinition;
  onWorkflowChange: (workflow: WorkflowDefinition) => void;
};

const wikiKinds = ['世界观硬设定', '人物状态', '人物关系', '伏笔状态', '章节摘要'];
const qualityChecks = ['连续性', '人物一致性', '世界观冲突', '伏笔推进', '重复度', '模板味风险'];

export function RuntimeLayerInspector({ kind, workflow, onWorkflowChange }: Props) {
  return (
    <aside className="inspector runtime-layer-inspector">
      <div className="inspector-head">
        <p className="eyebrow">Runtime Layer Inspector</p>
        <h2>{kind === 'wiki' ? 'Wiki 横切配置' : '质量阀门配置'}</h2>
      </div>
      {kind === 'wiki' ? <WikiLayerConfig workflow={workflow} onWorkflowChange={onWorkflowChange} /> : <QualityLayerConfig workflow={workflow} onWorkflowChange={onWorkflowChange} />}
    </aside>
  );
}

function WikiLayerConfig({ workflow, onWorkflowChange }: { workflow: WorkflowDefinition; onWorkflowChange: (workflow: WorkflowDefinition) => void }) {
  return (
    <>
      <section className="config-section">
        <h3><Database size={15} />读取 / 写回策略</h3>
        <div className="layer-option-grid">
          <label>
            读取范围
            <select defaultValue="project_recent">
              <option value="project_recent">项目全局 + 最近章节</option>
              <option value="strict_stage">仅当前阶段相关</option>
              <option value="wide_context">宽上下文检索</option>
            </select>
          </label>
          <label>
            写回策略
            <select defaultValue="append_with_conflict_check">
              <option value="append_with_conflict_check">追加写回 + 冲突检查</option>
              <option value="manual_review">人工确认后写回</option>
              <option value="append_only">只追加不覆盖</option>
            </select>
          </label>
        </div>
        <div className="constraint-chips layer-chips">
          {wikiKinds.map((item) => <span key={item}>{item}</span>)}
        </div>
      </section>
      <section className="config-section">
        <h3><RotateCcw size={15} />阶段读写开关</h3>
        <div className="layer-stage-list">
          {workflow.nodes.map((stage) => (
            <article key={stage.id}>
              <strong>{stage.label}</strong>
              <label><input checked={stage.memory_policy.read} readOnly type="checkbox" />读取</label>
              <label><input checked={stage.memory_policy.write} readOnly type="checkbox" />写回</label>
            </article>
          ))}
        </div>
        <p className="settings-note">本轮为横切配置展示层，读写策略仍使用阶段 memory policy；后续可接入细粒度编辑。</p>
      </section>
      <button className="tech-button inspector-save" onClick={() => onWorkflowChange({ ...workflow })} type="button">确认配置</button>
    </>
  );
}

function QualityLayerConfig({ workflow, onWorkflowChange }: { workflow: WorkflowDefinition; onWorkflowChange: (workflow: WorkflowDefinition) => void }) {
  const globalMin = Math.min(...workflow.nodes.filter((stage) => stage.type !== 'export_artifact').map((stage) => stage.quality_policy.min_score));
  return (
    <>
      <section className="config-section">
        <h3><ShieldCheck size={15} />全局阀门</h3>
        <div className="layer-option-grid">
          <label>
            全局最低分
            <input readOnly type="number" value={globalMin.toFixed(2)} />
          </label>
          <label>
            失败策略
            <select defaultValue="block_or_retry">
              <option value="block_or_retry">低于阈值则重试/阻断</option>
              <option value="warn_only">只警告不阻断</option>
              <option value="human_review">人工确认后继续</option>
            </select>
          </label>
        </div>
        <div className="constraint-chips layer-chips">
          {qualityChecks.map((item) => <span key={item}>{item}</span>)}
        </div>
      </section>
      <section className="config-section">
        <h3><SlidersHorizontal size={15} />阶段阈值</h3>
        <div className="layer-stage-list quality">
          {workflow.nodes.filter((stage) => stage.type !== 'export_artifact').map((stage) => (
            <article key={stage.id}>
              <strong>{stage.label}</strong>
              <span>Q {stage.quality_policy.min_score.toFixed(2)}</span>
              <em>{stage.quality_policy.retry_on_fail ? '失败重试' : '只记录'}</em>
            </article>
          ))}
        </div>
        <p className="settings-note">质量阀门仍是 runtime layer，不作为执行节点；阶段细节可在普通阶段配置中继续调整。</p>
      </section>
      <button className="tech-button inspector-save" onClick={() => onWorkflowChange({ ...workflow })} type="button">确认配置</button>
    </>
  );
}
