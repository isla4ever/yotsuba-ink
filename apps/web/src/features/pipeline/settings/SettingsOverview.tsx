import { AlertTriangle, ArrowUpRight, CheckCircle2, Info, RotateCcw } from 'lucide-react';
import type { ReactNode } from 'react';
import type { SettingsSectionId, SettingsSectionSummary } from '../contracts';

type Props = {
  activeEditorId: SettingsSectionId | null;
  children?: ReactNode;
  sections: SettingsSectionSummary[];
  onEditRequest: (section: SettingsSectionSummary) => void;
  onResetStageExceptions: () => void;
};

export function SettingsOverview({ activeEditorId, children, sections, onEditRequest, onResetStageExceptions }: Props) {
  return (
    <div className="settings-overview">
      <div className="settings-overview-list">
        {sections.map((section) => {
          const Icon = statusIcon(section);
          const active = activeEditorId === section.id;
          const titleId = `settings-section-${section.id}`;
          return (
            <section
              aria-labelledby={titleId}
              className={active ? 'active' : ''}
              data-status={section.status}
              key={section.id}
            >
              <div aria-hidden className="settings-overview-status"><Icon size={17} /></div>
              <div className="settings-overview-copy">
                <h3 id={titleId}>{section.title}</h3>
                {section.summary.map((line) => <p key={line}>{line}</p>)}
              </div>
              <div className="settings-overview-actions">
                {section.id === 'stage-exceptions' && section.status === 'warning' ? (
                  <button aria-label="全部恢复默认 AI 服务" className="settings-reset-exceptions" title="全部恢复默认 AI 服务" type="button" onClick={onResetStageExceptions}><RotateCcw size={14} /></button>
                ) : null}
                {section.action ? (
                  <button
                    aria-expanded={section.id === 'creation-mode' ? active : undefined}
                    className="settings-overview-action"
                    type="button"
                    onClick={() => onEditRequest(section)}
                  >
                    {section.action.label}<ArrowUpRight aria-hidden size={14} />
                  </button>
                ) : null}
              </div>
            </section>
          );
        })}
      </div>
      {children ? <div className="settings-inline-editor">{children}</div> : null}
    </div>
  );
}

function statusIcon(section: SettingsSectionSummary) {
  if (section.status === 'blocked') return AlertTriangle;
  if (section.status === 'warning') return AlertTriangle;
  if (section.status === 'ready') return CheckCircle2;
  return Info;
}
