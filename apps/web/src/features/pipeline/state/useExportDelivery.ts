import { useCallback, useEffect, useState } from 'react';
import type { ExportReceipt } from '../contracts';
import type { ExportArtifactVnext } from '../running/artifactsVnext';
import { downloadRunExportReceipt, listRunExports } from '../services/runHistoryApi';

type DeliveryState = {
  receipt: ExportReceipt | null;
  status: 'idle' | 'loading' | 'ready' | 'missing' | 'error' | 'downloading';
};

export function useExportDelivery(
  runId: string,
  artifact: ExportArtifactVnext | null,
  enabled: boolean,
  revision: string,
) {
  const [state, setState] = useState<DeliveryState>({ receipt: null, status: 'idle' });

  useEffect(() => {
    if (!enabled || !runId || !artifact) {
      setState({ receipt: null, status: 'idle' });
      return undefined;
    }
    const controller = new AbortController();
    setState({ receipt: null, status: 'loading' });
    void listRunExports(runId, controller.signal)
      .then((receipts) => {
        const receipt = receipts.find((item) => receiptMatchesArtifact(item, artifact)) ?? null;
        setState({ receipt, status: receipt ? 'ready' : 'missing' });
      })
      .catch((error: unknown) => {
        if (error instanceof DOMException && error.name === 'AbortError') return;
        setState({ receipt: null, status: 'error' });
      });
    return () => controller.abort();
  }, [artifact, enabled, revision, runId]);

  const download = useCallback(async () => {
    if (!state.receipt) return;
    const receipt = state.receipt;
    setState({ receipt, status: 'downloading' });
    try {
      const downloaded = await downloadRunExportReceipt(runId, receipt.export_id, {
        expectedSha256: receipt.sha256,
        expectedSizeBytes: receipt.size_bytes,
      });
      const url = URL.createObjectURL(downloaded.blob);
      const anchor = document.createElement('a');
      anchor.href = url;
      anchor.download = downloaded.filename;
      document.body.appendChild(anchor);
      anchor.click();
      anchor.remove();
      window.setTimeout(() => URL.revokeObjectURL(url), 0);
      setState({ receipt, status: 'ready' });
    } catch {
      setState({ receipt, status: 'error' });
    }
  }, [runId, state.receipt]);

  return { ...state, download };
}

export function receiptMatchesArtifact(receipt: ExportReceipt, artifact: ExportArtifactVnext) {
  return receipt.format === artifact.format
    && receipt.cover_asset_id === artifact.cover_asset_id
    && equalStrings(receipt.chapter_version_ids, artifact.chapter_version_ids)
    && receipt.metadata.title === artifact.metadata.title
    && receipt.metadata.author === artifact.metadata.author
    && receipt.metadata.version_note === artifact.metadata.version_note;
}

function equalStrings(left: string[], right: string[]) {
  return left.length === right.length && left.every((value, index) => value === right[index]);
}
