import { useCallback, useEffect, useRef } from 'react';

export type RunStreamSession = {
  id: number;
  signal: AbortSignal;
};

export function useRunSession() {
  const activeAbortRef = useRef<AbortController | null>(null);
  const sessionIdRef = useRef(0);
  const inFlightRef = useRef(false);

  const invalidate = useCallback(() => {
    sessionIdRef.current += 1;
    activeAbortRef.current?.abort();
    activeAbortRef.current = null;
    inFlightRef.current = false;
  }, []);

  const begin = useCallback((): RunStreamSession => {
    activeAbortRef.current?.abort();
    const controller = new AbortController();
    activeAbortRef.current = controller;
    sessionIdRef.current += 1;
    inFlightRef.current = true;
    return { id: sessionIdRef.current, signal: controller.signal };
  }, []);

  const isCurrent = useCallback((sessionId: number) => (
    sessionIdRef.current === sessionId
  ), []);

  const isInFlight = useCallback(() => inFlightRef.current, []);

  const release = useCallback((sessionId: number) => {
    if (sessionIdRef.current !== sessionId) return false;
    activeAbortRef.current = null;
    inFlightRef.current = false;
    return true;
  }, []);

  useEffect(() => invalidate, [invalidate]);

  return {
    begin,
    invalidate,
    isCurrent,
    isInFlight,
    release,
  };
}

export function isRunAbortError(error: unknown) {
  return (error instanceof DOMException && error.name === 'AbortError')
    || (error instanceof Error && error.name === 'AbortError');
}
