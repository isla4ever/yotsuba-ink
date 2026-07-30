import { useEffect, useMemo, useRef, useState } from 'react';
import type { ExportFormat, ExportMetadata, ExportReceipt } from '../contracts';
import { verifyExportBlob } from '../services/exportIntegrity';
import { downloadRunExportPackage, downloadRunExportPreview } from '../services/runApi';
import { downloadRunExportReceipt, listRunExports } from '../services/runHistoryApi';
import { ExportDeliveryPanel } from './ExportDeliveryPanel';
import { ExportDeliveryTrack } from './ExportDeliveryTrack';
import { ExportSelectionPanel } from './ExportSelectionPanel';
import {
  exportSelectionKey,
  exportSelectionsEqual,
  freezeExportSelection,
  normalizeExportMetadata,
  toggleExportChapter,
  type ExportSelectionSnapshot,
} from './exportSelectionModel';
import { exportArtifact } from './stageArtifacts';
import { StageToast } from './StageToast';

type Props = {
  activeRunId: string;
  result: string;
};

export function ExportStageView({ activeRunId, result }: Props) {
  const artifact = useMemo(() => exportArtifact(result), [result]);
  const chapters = artifact.chapters ?? [];
  const chapterIds = chapters.map((chapter) => chapter.id).join('\u0000');
  const [selected, setSelected] = useState<string[]>(() => chapters.map((chapter) => chapter.id));
  const [format, setFormat] = useState<ExportFormat>(() => artifact.formats.includes(artifact.default_format) ? artifact.default_format : artifact.formats[0] ?? 'md');
  const [metadata, setMetadata] = useState<ExportMetadata>(() => normalizeExportMetadata(artifact.metadata));
  const [generating, setGenerating] = useState(false);
  const [downloading, setDownloading] = useState(false);
  const [previewing, setPreviewing] = useState(false);
  const [previewed, setPreviewed] = useState(false);
  const [activeSelection, setActiveSelection] = useState<ExportSelectionSnapshot | null>(null);
  const [generatedSelection, setGeneratedSelection] = useState<ExportSelectionSnapshot | null>(null);
  const [receipt, setReceipt] = useState<ExportReceipt | null>(null);
  const [error, setError] = useState('');
  const [toast, setToast] = useState('');
  const requestRef = useRef<{ id: string; selectionKey: string } | null>(null);
  const requestAbortRef = useRef<AbortController | null>(null);
  const receiptAbortRef = useRef<AbortController | null>(null);
  const runIdRef = useRef(activeRunId);
  const currentSelection = useMemo(() => freezeExportSelection({ chapter_ids: selected, format, metadata }), [format, metadata, selected]);
  const selectionChanged = Boolean(generatedSelection && !exportSelectionsEqual(generatedSelection, currentSelection));

  useEffect(() => {
    runIdRef.current = activeRunId;
    requestAbortRef.current?.abort();
    receiptAbortRef.current?.abort();
    requestAbortRef.current = null;
    receiptAbortRef.current = null;
    requestRef.current = null;
    setSelected(chapters.map((chapter) => chapter.id));
    setFormat(artifact.formats.includes(artifact.default_format) ? artifact.default_format : artifact.formats[0] ?? 'md');
    setMetadata(normalizeExportMetadata(artifact.metadata));
    setGenerating(false);
    setDownloading(false);
    setPreviewing(false);
    setPreviewed(false);
    setActiveSelection(null);
    setGeneratedSelection(null);
    setReceipt(null);
    setError('');
    setToast('');
  }, [activeRunId]);

  useEffect(() => {
    if (!activeRunId) return undefined;
    const controller = new AbortController();
    const requestRunId = activeRunId;
    receiptAbortRef.current = controller;
    void listRunExports(requestRunId, controller.signal).then((items) => {
      if (controller.signal.aborted || runIdRef.current !== requestRunId || !items.length) return;
      const latest = items[0];
      setGeneratedSelection(freezeExportSelection({ chapter_ids: latest.chapter_ids, format: latest.format, metadata: latest.metadata }));
      setReceipt(latest);
    }).catch((reason: unknown) => {
      if (controller.signal.aborted || runIdRef.current !== requestRunId) return;
      setError(reason instanceof Error ? reason.message : '导出历史加载失败，请稍后重试。');
    }).finally(() => {
      if (receiptAbortRef.current === controller) receiptAbortRef.current = null;
    });
    return () => controller.abort();
  }, [activeRunId]);

  useEffect(() => () => {
    requestAbortRef.current?.abort();
    receiptAbortRef.current?.abort();
  }, []);

  useEffect(() => {
    if (!chapterIds || generating) return;
    const valid = new Set(chapterIds.split('\u0000'));
    setSelected((current) => {
      const kept = current.filter((id) => valid.has(id));
      return kept.length ? kept : [...valid];
    });
  }, [chapterIds, generating]);

  const showToast = (message: string) => {
    setToast(message);
  };
  const toggleChapter = (id: string) => {
    if (generating) return;
    setSelected((current) => toggleExportChapter(chapters.map((chapter) => chapter.id), current, id));
  };
  const selectAll = () => {
    if (generating) return;
    setSelected((current) => current.length === chapters.length ? [] : chapters.map((chapter) => chapter.id));
  };
  const generateExport = async () => {
    if (!currentSelection.chapter_ids.length || !activeRunId || generating || !artifact.package_ready) return;
    const frozen = freezeExportSelection(currentSelection);
    const selectionKey = exportSelectionKey(frozen);
    if (!requestRef.current || requestRef.current.selectionKey !== selectionKey) {
      requestRef.current = { id: createExportRequestId(), selectionKey };
    }
    const requestId = requestRef.current.id;
    const requestRunId = activeRunId;
    const controller = new AbortController();
    receiptAbortRef.current?.abort();
    receiptAbortRef.current = null;
    requestAbortRef.current?.abort();
    requestAbortRef.current = controller;
    setGenerating(true);
    setActiveSelection(frozen);
    setError('');
    try {
      const downloaded = await downloadRunExportPackage(requestRunId, frozen.format, frozen.chapter_ids, requestId, frozen.metadata, controller.signal);
      if (controller.signal.aborted || runIdRef.current !== requestRunId) return;
      const receipts = await listRunExports(requestRunId, controller.signal);
      const savedReceipt = receipts.find((item) => item.export_id === downloaded.export_id);
      if (!savedReceipt) throw new Error('交付文件已生成，但没有找到对应的交付记录。');
      await verifyExportBlob(downloaded.blob, {
        expectedSha256: savedReceipt.sha256,
        expectedSizeBytes: savedReceipt.size_bytes,
        requireResponseSha256: true,
        responseSha256: downloaded.sha256,
      });
      setGeneratedSelection(freezeExportSelection({
        chapter_ids: savedReceipt.chapter_ids,
        format: savedReceipt.format,
        metadata: savedReceipt.metadata,
      }));
      setReceipt(savedReceipt);
      triggerBlobDownload(downloaded.blob, downloaded.filename);
      showToast(`${downloaded.filename} 已生成并开始下载`);
      requestRef.current = null;
    } catch (reason) {
      if (controller.signal.aborted || runIdRef.current !== requestRunId) return;
      setError(reason instanceof Error ? reason.message : '导出包生成失败，请检查校验状态后重试。');
    } finally {
      if (requestAbortRef.current === controller) {
        requestAbortRef.current = null;
        setGenerating(false);
        setActiveSelection(null);
      }
    }
  };
  const downloadPreview = async () => {
    if (!currentSelection.chapter_ids.length || !activeRunId || previewing || generating) return;
    const controller = new AbortController();
    const requestRunId = activeRunId;
    setPreviewing(true);
    setError('');
    try {
      const downloaded = await downloadRunExportPreview(requestRunId, currentSelection.format, currentSelection.chapter_ids, currentSelection.metadata, controller.signal);
      if (runIdRef.current !== requestRunId) return;
      triggerBlobDownload(downloaded.blob, downloaded.filename);
      setPreviewed(true);
      showToast(`${downloaded.filename} 已生成并开始下载`);
    } catch (reason) {
      if (runIdRef.current !== requestRunId) return;
      setError(reason instanceof Error ? reason.message : '预览稿生成失败，请稍后重试。');
    } finally {
      if (runIdRef.current === requestRunId) setPreviewing(false);
    }
  };
  const redownloadExport = async () => {
    if (!activeRunId || !receipt || downloading || generating) return;
    const controller = new AbortController();
    const requestRunId = activeRunId;
    receiptAbortRef.current?.abort();
    receiptAbortRef.current = controller;
    setDownloading(true);
    setError('');
    try {
      const downloaded = await downloadRunExportReceipt(requestRunId, receipt.export_id, {
        expectedSha256: receipt.sha256,
        expectedSizeBytes: receipt.size_bytes,
        signal: controller.signal,
      });
      if (controller.signal.aborted || runIdRef.current !== requestRunId) return;
      triggerBlobDownload(downloaded.blob, downloaded.filename);
      showToast(`${downloaded.filename} 已开始下载`);
    } catch (reason) {
      if (controller.signal.aborted || runIdRef.current !== requestRunId) return;
      setError(reason instanceof Error ? reason.message : '重新下载失败，请稍后重试。');
    } finally {
      if (receiptAbortRef.current === controller) {
        receiptAbortRef.current = null;
        setDownloading(false);
      }
    }
  };

  return (
    <div className="export-workbench">
      <StageToast message={toast} onDismiss={() => setToast('')} />
      <ExportDeliveryTrack finalReady={Boolean(receipt)} previewReady={previewed} selected={selected.length} total={chapters.length} />
      <ExportSelectionPanel
        chapters={chapters}
        format={format}
        formats={artifact.formats}
        locked={generating}
        metadata={metadata}
        onFormatChange={setFormat}
        onMetadataChange={setMetadata}
        onSelectAll={selectAll}
        onToggleChapter={toggleChapter}
        selected={selected}
      />
      <ExportDeliveryPanel
        activeSelection={activeSelection}
        artifact={artifact}
        currentSelection={currentSelection}
        downloading={downloading}
        error={error}
        generatedSelection={generatedSelection}
        generating={generating}
        onDownload={() => { void redownloadExport(); }}
        onGenerate={() => { void generateExport(); }}
        onPreview={() => { void downloadPreview(); }}
        previewing={previewing}
        receipt={receipt}
        selectionChanged={selectionChanged}
      />
    </div>
  );
}

function createExportRequestId() {
  const id = typeof crypto !== 'undefined' && 'randomUUID' in crypto
    ? crypto.randomUUID()
    : `${Date.now()}-${Math.random().toString(16).slice(2)}`;
  return `export-ui-${id}`;
}

function triggerDownload(url: string, filename: string) {
  const anchor = document.createElement('a');
  anchor.href = url;
  anchor.download = filename;
  anchor.style.display = 'none';
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
}

function triggerBlobDownload(blob: Blob, filename: string) {
  const url = URL.createObjectURL(blob);
  triggerDownload(url, filename);
  window.setTimeout(() => URL.revokeObjectURL(url), 1000);
}
