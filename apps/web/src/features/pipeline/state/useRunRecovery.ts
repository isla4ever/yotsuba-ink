import { useCallback, useEffect, useMemo, useRef } from 'react';
import { getRun, isRunNotFoundError } from '../services/runApi';
import type { StoredRunControlState } from './storage';
import {
  resolveServerRunPresentation,
  resolveServerRunRecovery,
  type HydratedRunState,
  type RunRecoveryDiscardReason,
  type RunRecoveryResolution,
} from './runState';

type RunLoader = typeof getRun;

type RunRecoveryHandlers = {
  onDiscard: (reason: RunRecoveryDiscardReason) => void;
  onRestore: (state: HydratedRunState, reconnect: boolean) => void | Promise<void>;
  onSettled?: () => void;
  onWarning: (message: string) => void;
};

type UseRunRecoveryOptions = RunRecoveryHandlers & {
  enabled?: boolean;
  loadRun?: RunLoader;
  /**
   * Booting straight onto a read-only run surface (the console): a finished run
   * must still be presented there, instead of being dropped as a stale session.
   */
  presentTerminalRuns?: boolean;
  stored: StoredRunControlState;
};

export type InitialRunRecoveryControl = {
  cancel: () => void;
};

type ActiveRunRecovery = {
  active: boolean;
  controller: AbortController;
};

export function useRunRecovery({
  enabled = true,
  loadRun = getRun,
  presentTerminalRuns = false,
  stored,
  ...handlers
}: UseRunRecoveryOptions) {
  const handlersRef = useRef<RunRecoveryHandlers>(handlers);
  const activeRecoveryRef = useRef<ActiveRunRecovery | null>(null);
  const cancelledRef = useRef(false);
  handlersRef.current = handlers;

  const cancel = useCallback(() => {
    cancelledRef.current = true;
    handlersRef.current.onSettled?.();
    const recovery = activeRecoveryRef.current;
    activeRecoveryRef.current = null;
    if (!recovery) return;
    recovery.active = false;
    recovery.controller.abort();
  }, []);

  const control = useMemo<InitialRunRecoveryControl>(() => ({ cancel }), [cancel]);

  useEffect(() => {
    if (!enabled || !stored.activeRunId || cancelledRef.current) return undefined;
    const controller = new AbortController();
    const recovery: ActiveRunRecovery = { active: true, controller };
    activeRecoveryRef.current = recovery;

    async function recover() {
      try {
        const snapshot = await loadRun(stored.activeRunId, controller.signal);
        if (!recovery.active) return;
        const resolve = presentTerminalRuns ? resolveServerRunPresentation : resolveServerRunRecovery;
        dispatchRecovery(resolve(snapshot, stored.activeRunId), handlersRef.current);
      } catch (error) {
        if (!recovery.active || isAbortError(error)) return;
        if (isRunNotFoundError(error)) {
          handlersRef.current.onDiscard('not_found');
          handlersRef.current.onWarning('上次运行已不存在，已清理本地恢复点。');
          return;
        }
        handlersRef.current.onWarning('暂时无法读取 LangGraph 运行状态；本地缓存不会接管恢复权威，请稍后重试。');
      } finally {
        if (activeRecoveryRef.current === recovery) activeRecoveryRef.current = null;
        handlersRef.current.onSettled?.();
      }
    }

    void recover();
    return () => {
      if (activeRecoveryRef.current === recovery) activeRecoveryRef.current = null;
      recovery.active = false;
      controller.abort();
    };
  }, [enabled, loadRun, presentTerminalRuns, stored]);

  return control;
}

function dispatchRecovery(
  resolution: RunRecoveryResolution,
  handlers: RunRecoveryHandlers,
) {
  if (resolution.kind === 'discard') {
    handlers.onDiscard(resolution.reason);
    if (resolution.reason === 'invalid') {
      handlers.onWarning('上次运行缺少有效的已保存状态，已清理本机恢复点。');
    }
    if (resolution.reason === 'failed') {
      handlers.onWarning('上次运行已失败，已退出活动运行；可检查历史记录后重新开始。');
    }
    return;
  }
  void handlers.onRestore(resolution.hydrated, resolution.reconnect);
}

function isAbortError(error: unknown) {
  return (error instanceof DOMException && error.name === 'AbortError')
    || (error instanceof Error && error.name === 'AbortError');
}
