import { AlertTriangle, Building2, CheckCircle2, Edit3, FileCheck2, Globe2, MapPinned, RefreshCw, Scale3D, type LucideIcon } from 'lucide-react';
import { useEffect, useRef, useState } from 'react';
import type { QualityMode, WorkflowStage } from '../contracts';
import { LoadingButton } from '../layout/LoadingButton';
import { DraftRegenerationDialog } from './DraftRegenerationDialog';
import { InfoTagEditor, InfoTitlePicker } from './InfoBriefFields';
import { InfoCharacterRoster } from './InfoCharacterRoster';
import { InfoGuardrailsDisclosure } from './InfoGuardrailsDisclosure';
import { infoRecommendationReadiness, normalizeRecommendation, type InfoRecommendation } from './infoRecommendationModel';
import { infoWorldbuildingDigest, type InfoWorldbuildingDigestKey } from './infoWorldbuildingDigest';
import { StageFinalizeTray } from './StageFinalizeTray';
import { TERM } from '../lib/terminology';

type Props = {
  approvalDraft: string;
  approvalPending: boolean;
  qualityMode: QualityMode;
  regenerationFailed: boolean;
  stage: WorkflowStage;
  onApprovalDraftChange: (value: string) => void;
  onApproveBrief: (artifact: string) => Promise<boolean>;
  onEditCharacter: () => void;
  onEditWorldbuilding: () => void;
  onRegenerateBrief: (direction?: string) => Promise<boolean>;
};

export function InfoRecommendationView({
  approvalDraft,
  approvalPending,
  onApprovalDraftChange,
  onApproveBrief,
  onEditCharacter,
  onEditWorldbuilding,
  onRegenerateBrief,
  qualityMode,
  regenerationFailed,
  stage,
}: Props) {
  const [dialogOpen, setDialogOpen] = useState(false);
  const [tagDraft, setTagDraft] = useState('');
  const [confirming, setConfirming] = useState(false);
  const regenerateButtonRef = useRef<HTMLButtonElement>(null);
  const recommendation = normalizeRecommendation(approvalDraft, stage);
  const readiness = infoRecommendationReadiness(recommendation);
  const readOnly = !approvalPending;

  useEffect(() => {
    if (regenerationFailed) regenerateButtonRef.current?.focus();
  }, [regenerationFailed]);

  const updateDraft = (patch: Partial<InfoRecommendation>) => {
    onApprovalDraftChange(JSON.stringify({ ...recommendation, ...patch }, null, 2));
  };

  const addTag = (value: string) => {
    const tag = value.trim();
    if (!tag || recommendation.tags.includes(tag)) return;
    updateDraft({ tags: [...recommendation.tags, tag].slice(0, 8) });
    setTagDraft('');
  };

  const confirmRecommendation = async () => {
    setConfirming(true);
    try {
      await onApproveBrief(JSON.stringify(recommendation, null, 2));
    } finally {
      setConfirming(false);
    }
  };

  return (
    <section aria-busy={confirming} className="info-recommendation-board">
      <div className="info-brief-workbench">
        <header className="info-brief-context-bar">
          <div><p className="eyebrow">创作立项</p><h2>小说信息定稿</h2></div>
          <div className={`info-brief-readiness ${readiness.ready ? 'ready' : 'incomplete'}`}>
            <FileCheck2 size={15} />
            <span>{readiness.completed}/{readiness.total}</span>
            <b>{approvalPending ? (readiness.ready ? '可以确认' : `待补：${readiness.missingLabels.join('、')}`) : '已定稿'}</b>
          </div>
        </header>

        <div className="info-brief-primary">
          <InfoTitlePicker onChange={updateDraft} readOnly={readOnly} recommendation={recommendation} />
          <InfoTagEditor
            draft={tagDraft}
            onAdd={addTag}
            onDraftChange={setTagDraft}
            onRemove={(tag) => updateDraft({ tags: recommendation.tags.filter((item) => item !== tag) })}
            readOnly={readOnly}
            tags={recommendation.tags}
          />
          <label className="recommendation-field synopsis compact-synopsis">
            <span>小说简介</span>
            <textarea readOnly={readOnly} value={recommendation.synopsis} onChange={(event) => updateDraft({ synopsis: event.target.value })} />
          </label>
        </div>

        <div className="info-brief-support-grid">
          <WorldbuildingDigest onEdit={onEditWorldbuilding} readOnly={readOnly} recommendation={recommendation} />
          <InfoCharacterRoster onEdit={onEditCharacter} readOnly={readOnly} recommendation={recommendation} />
        </div>
        <InfoGuardrailsDisclosure onChange={updateDraft} readOnly={readOnly} recommendation={recommendation} />
      </div>

      <StageFinalizeTray className="info-finalize-tray" open={approvalPending}>
        <div className="recommendation-footer inline-footer">
          <p className={regenerationFailed ? 'info-regeneration-failure' : ''} role={regenerationFailed ? 'alert' : undefined}>
            {regenerationFailed
              ? '换一稿未完成，当前稿已保留。可调整方向后重试。'
              : '当前稿会在确认成功后成为梗概、大纲、细纲和正文的共同基线。'}
          </p>
          <div className="approval-action-row compact">
            <button className="ghost tiny-action" disabled={!recommendation.selected_title.trim() || confirming} onClick={() => setDialogOpen(true)} ref={regenerateButtonRef} type="button"><RefreshCw size={13} />换一稿</button>
            <LoadingButton aria-label="确认定稿" className="tech-button" disabled={!readiness.ready || confirming} loading={confirming} loadingLabel="提交中" onClick={() => void confirmRecommendation()}>
              <CheckCircle2 size={14} />{TERM.confirmFinal}
            </LoadingButton>
          </div>
        </div>
      </StageFinalizeTray>

      <DraftRegenerationDialog
        mode={qualityMode}
        onClose={() => setDialogOpen(false)}
        onConfirm={(direction) => {
          setDialogOpen(false);
          void onRegenerateBrief(direction);
        }}
        open={dialogOpen}
        stage={stage}
      />
    </section>
  );
}

function WorldbuildingDigest({ onEdit, readOnly, recommendation }: { onEdit: () => void; readOnly: boolean; recommendation: InfoRecommendation }) {
  const icons: Record<InfoWorldbuildingDigestKey, LucideIcon> = { groups: Building2, places: MapPinned, risks: AlertTriangle, rules: Scale3D };
  const sections = infoWorldbuildingDigest(recommendation.worldbuilding_detail).map((item) => ({ ...item, icon: icons[item.key] }));
  const structured = sections.some((item) => item.value !== '待补充');
  return (
    <section className="info-worldbuilding-digest">
      <div className="info-worldbuilding-head">
        <div><span><Globe2 size={15} />详细世界观</span><small>当前立项原稿摘要</small></div>
        <b>{recommendation.worldbuilding_detail.trim() ? '已填写' : '待补充'}</b>
        <button aria-label={readOnly ? '预览详细世界观' : '编辑详细世界观'} className="square-action-button" onClick={onEdit} title={readOnly ? '预览世界观' : '编辑世界观'} type="button"><Edit3 size={14} /></button>
      </div>
      <div className="info-worldbuilding-scroll">
        {structured
          ? sections.map((item) => <article className="info-worldbuilding-tile" key={item.label}><i><item.icon size={15} /></i><div><strong>{item.label}</strong><span>{item.value}</span></div></article>)
          : <p className="info-worldbuilding-raw-summary">{recommendation.worldbuilding_detail || '详细世界观待补充'}</p>}
      </div>
    </section>
  );
}
