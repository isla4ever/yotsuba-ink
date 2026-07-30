import { Check, CircleDashed, FileClock, PackageCheck, SlidersHorizontal } from 'lucide-react';

export function ExportDeliveryTrack({ finalReady, previewReady, selected, total }: { finalReady: boolean; previewReady: boolean; selected: number; total: number }) {
  const steps = [
    { icon: SlidersHorizontal, label: '交付准备', detail: `${selected}/${total} 章已选择`, ready: selected > 0, current: selected > 0 && !previewReady },
    { icon: FileClock, label: '预览稿', detail: previewReady ? '可变预览已下载' : '可随正文更新', ready: previewReady, current: selected > 0 && !previewReady },
    { icon: PackageCheck, label: '最终交付', detail: finalReady ? '不可变收据已生成' : '等待四项门禁', ready: finalReady, current: previewReady && !finalReady },
  ];
  return (
    <nav aria-label="交付进程" className="export-delivery-track">
      <div><span className="eyebrow">连续交付台</span><strong>准备、预览、最终版本</strong></div>
      {steps.map(({ current, detail, icon: Icon, label, ready }) => (
        <article className={`${ready ? 'ready' : ''}${current ? ' current' : ''}`} key={label}>
          <i>{ready ? <Check size={13} /> : <Icon size={13} />}</i>
          <span><strong>{label}</strong><small>{detail}</small></span>
          {label === '最终交付' && !ready ? <CircleDashed size={12} /> : null}
        </article>
      ))}
    </nav>
  );
}
