import { useId } from 'react';

type Props = {
  className?: string;
  size?: 'small' | 'medium';
};

const starPath = 'M63,37c-6.7-4-4-27-13-27s-6.3,23-13,27-27,4-27,13,20.3,9,27,13,4,27,13,27,6.3-23,13-27,27-4,27-13-20.3-9-27-13Z';

export function ButtonLoadingIndicator({ className = '', size = 'small' }: Props) {
  const instanceId = useId().replace(/:/g, '');
  return (
    <span aria-hidden="true" className={`nw-button-loader is-${size}${className ? ` ${className}` : ''}`}>
      {[0, 1, 2].map((index) => (
        <FlowingStar id={`nw-star-${instanceId}-${index}`} index={index} key={index} />
      ))}
    </span>
  );
}

function FlowingStar({ id, index }: { id: string; index: number }) {
  const shineId = `${id}-shine`;
  const maskId = `${id}-mask`;
  const shadowId = `${id}-shadow`;
  const lightId = `${id}-light`;
  const sideId = `${id}-side`;
  const baseId = `${id}-base`;
  return (
    <svg className={`nw-button-loader-star star-${index + 1}`} focusable="false" viewBox="0 0 100 100">
      <defs>
        <filter id={shineId}><feGaussianBlur stdDeviation="3" /></filter>
        <mask id={maskId}><path d={starPath} fill="white" /></mask>
        <radialGradient cx="50" cy="66" fx="50" fy="66" gradientTransform="translate(0 35) scale(1 .5)" gradientUnits="userSpaceOnUse" id={shadowId} r="30">
          <stop offset="0" stopColor="black" stopOpacity=".3" />
          <stop offset=".5" stopColor="black" stopOpacity=".1" />
          <stop offset="1" stopColor="black" stopOpacity="0" />
        </radialGradient>
        <radialGradient cx="55" cy="20" fx="55" fy="20" gradientUnits="userSpaceOnUse" id={lightId} r="30">
          <stop offset="0" stopColor="white" stopOpacity=".34" />
          <stop offset=".55" stopColor="white" stopOpacity=".1" />
          <stop offset="1" stopColor="white" stopOpacity="0" />
        </radialGradient>
        <radialGradient cx="85" cy="50" fx="85" fy="50" gradientUnits="userSpaceOnUse" id={sideId} r="30">
          <stop offset="0" stopColor="white" stopOpacity=".24" />
          <stop offset=".55" stopColor="white" stopOpacity=".08" />
          <stop offset="1" stopColor="white" stopOpacity="0" />
        </radialGradient>
        <linearGradient gradientUnits="userSpaceOnUse" id={baseId} x1="50" x2="50" y1="90" y2="10">
          <stop offset="0" stopColor="black" stopOpacity=".22" />
          <stop offset=".45" stopColor="black" stopOpacity="0" />
        </linearGradient>
      </defs>
      <path d={starPath} fill="currentColor" />
      <path d={starPath} fill={`url(#${shadowId})`} />
      <path d={starPath} fill="none" filter={`url(#${shineId})`} mask={`url(#${maskId})`} opacity=".36" stroke="white" strokeWidth="3" />
      <path d={starPath} fill={`url(#${lightId})`} />
      <path d={starPath} fill={`url(#${sideId})`} />
      <path d={starPath} fill={`url(#${baseId})`} />
    </svg>
  );
}
