import type { CSSProperties, ReactNode } from 'react';

type AmbientSurfaceProps = {
  children?: ReactNode;
  className?: string;
  intensity?: 'soft' | 'strong';
};

export function AmbientSurface({ children, className = '', intensity = 'soft' }: AmbientSurfaceProps) {
  return (
    <div className={`ambient-surface ${intensity === 'strong' ? 'strong' : ''} ${className}`.trim()}>
      <span className="ambient-aurora" aria-hidden="true" />
      {children}
    </div>
  );
}

type SpotlightLayerProps = {
  className?: string;
  color?: string;
};

export function SpotlightLayer({ className = '', color = 'var(--mode-aura-soft)' }: SpotlightLayerProps) {
  return (
    <span
      aria-hidden="true"
      className={`spotlight-layer ${className}`.trim()}
      style={{ '--spotlight-color': color } as CSSProperties}
    />
  );
}

type EnergySurfaceProps = {
  className?: string;
};

export function EnergySurface({ className = '' }: EnergySurfaceProps) {
  return (
    <span className={`energy-button-surface ${className}`.trim()} aria-hidden="true">
      <span />
      <span />
    </span>
  );
}

type StarfieldLayerProps = {
  className?: string;
  meteors?: boolean;
};

export function StarfieldLayer({ className = '', meteors = true }: StarfieldLayerProps) {
  return (
    <span className={`starfield-layer ${className}`.trim()} aria-hidden="true">
      <span className="starfield-nebula" />
      <span className="starfield-stars stars-a" />
      <span className="starfield-stars stars-b" />
      {meteors ? <span className="starfield-meteor meteor-a" /> : null}
      {meteors ? <span className="starfield-meteor meteor-b" /> : null}
    </span>
  );
}
