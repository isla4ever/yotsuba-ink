import { useEffect, useState } from 'react';
import type { ChapterContextManifestRecord } from '../contracts';
import { getContextManifest, getRun } from '../services/runApi';

export type ChapterContextManifestState = {
  record: ChapterContextManifestRecord | null;
  status: 'idle' | 'loading' | 'ready' | 'unavailable';
  error: string;
};

const idle: ChapterContextManifestState = { record: null, status: 'idle', error: '' };

/** Reads the Graph read-model reference, then loads the immutable sidecar. */
export function useChapterContextManifest(
  runId: string,
  revision: number,
  enabled: boolean,
): ChapterContextManifestState {
  const [state, setState] = useState<{ key: string; value: ChapterContextManifestState }>({ key: '', value: idle });

  useEffect(() => {
    if (!enabled || !runId) {
      setState({ key: '', value: idle });
      return undefined;
    }

    const controller = new AbortController();
    const key = `${runId}:${revision}`;
    setState({ key, value: { record: null, status: 'loading', error: '' } });

    void getRun(runId, controller.signal)
      .then((envelope) => {
        const manifestId = envelope.read_model.context_manifest_ref;
        if (!manifestId) {
          setState({ key, value: { record: null, status: 'unavailable', error: '当前章节尚未生成 Context Manifest。' } });
          return null;
        }
        return getContextManifest(runId, manifestId, controller.signal);
      })
      .then((record) => {
        if (!record || controller.signal.aborted) return;
        setState({
          key,
          value: record.chapter_id
            ? { record, status: 'ready', error: '' }
            : { record: null, status: 'unavailable', error: 'Context Manifest 缺少章节身份。' },
        });
      })
      .catch((error: unknown) => {
        if (error instanceof DOMException && error.name === 'AbortError') return;
        const message = error instanceof Error ? error.message : 'Context Manifest 暂时不可用。';
        setState({ key, value: { record: null, status: 'unavailable', error: message } });
      });

    return () => controller.abort();
  }, [enabled, revision, runId]);

  return state.key === `${runId}:${revision}` ? state.value : enabled && runId
    ? { record: null, status: 'loading', error: '' }
    : idle;
}
