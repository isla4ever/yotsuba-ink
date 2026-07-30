import { forwardRef, type ButtonHTMLAttributes, type ReactNode } from 'react';
import { ButtonLoadingIndicator } from './ButtonLoadingIndicator';

type Props = ButtonHTMLAttributes<HTMLButtonElement> & {
  loading?: boolean;
  loadingLabel?: ReactNode;
};

export const LoadingButton = forwardRef<HTMLButtonElement, Props>(function LoadingButton({
  children,
  className = '',
  disabled,
  loading = false,
  loadingLabel = '处理中',
  type = 'button',
  ...buttonProps
}, ref) {
  return (
    <button
      {...buttonProps}
      aria-busy={loading || undefined}
      className={`nw-loading-button${className ? ` ${className}` : ''}`}
      data-loading={loading || undefined}
      disabled={disabled || loading}
      ref={ref}
      type={type}
    >
      <span aria-hidden={loading || undefined} className="nw-loading-button-content">{children}</span>
      {loading ? (
        <span className="nw-loading-button-state">
          <ButtonLoadingIndicator />
          {loadingLabel == null ? <span className="visually-hidden">处理中</span> : <span>{loadingLabel}</span>}
        </span>
      ) : null}
    </button>
  );
});
