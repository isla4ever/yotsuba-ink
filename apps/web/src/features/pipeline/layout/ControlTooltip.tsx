import { cloneElement, useId, type ReactElement } from 'react';

export function ControlTooltip({ children, label }: { children: ReactElement<{ 'aria-describedby'?: string }>; label: string }) {
  const tooltipId = useId();
  return (
    <span className="control-tooltip-trigger">
      {cloneElement(children, { 'aria-describedby': tooltipId })}
      <span className="control-tooltip" id={tooltipId} role="tooltip">{label}</span>
    </span>
  );
}
