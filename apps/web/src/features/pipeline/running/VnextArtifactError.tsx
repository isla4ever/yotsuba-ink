import { ShieldAlert } from 'lucide-react';

export function VnextArtifactError({ errors, label }: { errors: string[]; label: string }) {
  return (
    <section className="stage-run-card vnext-artifact-error">
      <ShieldAlert size={18} />
      <div><strong>{label}合同未通过</strong><span>{errors[0] ?? '缺少有效阶段产物'}</span></div>
    </section>
  );
}
