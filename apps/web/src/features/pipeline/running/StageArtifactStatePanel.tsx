import { AlertTriangle, ArrowLeft, Braces } from 'lucide-react';
import type { StageType } from '../contracts';
import { ManuscriptLoadingIndicator } from '../layout/ManuscriptLoadingIndicator';
import type { StageArtifactState } from './stageArtifactState';
import { stageEmptyStateAction, stageEmptyStateHint } from './stageEmptyState';

type Props = {
  label: string;
  onReturn?: () => void;
  runStarted: boolean;
  stageType: StageType;
  state: StageArtifactState;
};

export function StageArtifactStatePanel({ label, onReturn, runStarted, stageType, state }: Props) {
  if (state.status === 'ready') return null;
  const config = stateConfig(label, stageType, state);
  const showReturn = Boolean(onReturn) && (state.status === 'error' || state.status === 'invalid' || state.status === 'empty');
  const returnLabel = state.status === 'empty' ? stageEmptyStateAction(runStarted) : '返回流水线工作台';
  return (
    <section
      aria-live={state.status === 'error' || state.status === 'invalid' ? 'assertive' : 'polite'}
      className={`stage-artifact-state app-feedback-state ${state.status === 'error' || state.status === 'invalid' ? 'app-error-state' : state.status === 'empty' ? 'app-empty-state' : ''} ${state.status}`}
      role={state.status === 'error' || state.status === 'invalid' ? 'alert' : 'status'}
    >
      <div className="stage-artifact-state-icon">
        {state.status === 'streaming' ? <ManuscriptLoadingIndicator size="compact" /> : <config.icon size={22} />}
      </div>
      <div>
        <p className="eyebrow">产物状态</p>
        <h3>{config.title}</h3>
        <p>{config.description}</p>
        {state.status === 'streaming' && state.sections.length ? (
          <div className="stage-artifact-stream-sections">
            {state.sections.map((section) => <span key={section}>{section}</span>)}
          </div>
        ) : null}
        {showReturn ? (
          <button className="ghost tiny-action app-feedback-action" onClick={onReturn} type="button"><ArrowLeft size={14} />{returnLabel}</button>
        ) : null}
      </div>
    </section>
  );
}

export function ArtifactFixtureNotice() {
  return <div className="artifact-fixture-notice"><AlertTriangle size={14} />当前展示为演示数据，不会写入真实运行。</div>;
}

function stateConfig(label: string, stageType: StageType, state: Exclude<StageArtifactState, { status: 'ready' }>) {
  if (state.status === 'streaming') return {
    icon: Braces,
    title: `${label}正在生成`,
    description: state.sections.length ? '内容正在持续写入，完成结构检查后将展示可编辑产物。' : '阶段执行已启动，正在等待首个有效片段。',
  };
  if (state.status === 'invalid') return { icon: Braces, title: '产物结构检查未通过', description: state.message };
  if (state.status === 'error') return { icon: AlertTriangle, title: '阶段执行失败', description: state.message };
  return { icon: Braces, title: '尚无阶段产物', description: stageEmptyStateHint(stageType) };
}
