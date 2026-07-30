import { CheckCircle2, CircleAlert, Save } from 'lucide-react';

type Props = {
  className?: string;
  disabled?: boolean;
  dirty: boolean;
  invalidCount?: number;
  label?: string;
  onClose: () => void;
  onSave: () => void;
};

export function ArtifactDraftActions({ className = '', disabled = false, dirty, invalidCount = 0, label = '保存到当前稿', onClose, onSave }: Props) {
  const status = invalidCount > 0
    ? `还有 ${invalidCount} 项必填内容待补充`
    : dirty
      ? '未保存修改'
      : '当前稿未修改';

  return (
    <footer className={`artifact-dialog-actions artifact-draft-actions${className ? ` ${className}` : ''}`}>
      <span className={`artifact-draft-status${invalidCount ? ' error' : dirty ? ' dirty' : ''}`} aria-live="polite">
        {invalidCount || dirty ? <CircleAlert size={14} /> : <CheckCircle2 size={14} />}
        {status}
      </span>
      <button className="ghost tiny-action" onClick={onClose} type="button">取消</button>
      <button className="mode-primary-action" disabled={disabled || !dirty || invalidCount > 0} onClick={onSave} type="button">
        <Save size={14} />{label}
      </button>
    </footer>
  );
}
