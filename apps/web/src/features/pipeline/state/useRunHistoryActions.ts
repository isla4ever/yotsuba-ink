import { useCallback, type Dispatch, type SetStateAction } from 'react';
import type { ExportReceipt, RunControlState, RunHistoryItem, WorkflowDefinition } from '../contracts';
import { getRun } from '../services/runApi';
import {
  downloadRunExportReceipt,
  listRunSnapshots,
  restoreRunSnapshot,
} from '../services/runHistoryApi';
import type { RunSource } from '../lib/runSource';
import { projectIdForRun } from './projectScope';
import { resolveHistoricalRunOpen, type HydratedRunState } from './runState';

type Options = {
  activeRunId: string;
  cancelInitialRecovery: () => void;
  historyRefresh: () => Promise<void>;
  /**
   * Phase 11.2 (mine 5): before restoring, switch the shell to the project
   * that owns the run ('' = unarchived legacy run) instead of silently
   * overwriting the current project's workflow.
   */
  onProjectContext: (projectId: string) => Promise<void>;
  onRestore: (hydrated: HydratedRunState, reconnect: boolean) => Promise<void>;
  onWarning: (message: string) => void;
  runControlState: RunControlState;
  running: boolean;
  suppressWorkflowSave: (workflow: WorkflowDefinition) => void;
  setRunSource: (source: RunSource) => void;
  setWorkflow: Dispatch<SetStateAction<WorkflowDefinition>>;
  stopActiveStream: () => void;
};

export function useRunHistoryActions(options: Options) {
  const openRun = useCallback(async (item: RunHistoryItem) => {
    if (item.run_id === options.activeRunId) {
      try {
        const snapshot = await getRun(item.run_id);
        if (snapshot.workflow) {
          options.suppressWorkflowSave(snapshot.workflow);
          options.setWorkflow(snapshot.workflow);
        }
        options.onWarning('');
        return item.current_stage.id || snapshot.state?.current_stage_id || 'info';
      } catch (error) {
        options.onWarning(`读取当前运行配置失败：${errorMessage(error)}`);
        return '';
      }
    }
    if (options.activeRunId && (options.running || ['starting', 'running', 'stop_requested'].includes(options.runControlState))) {
      options.onWarning('当前运行仍在执行，请先暂停后再切换创作历史。');
      return '';
    }
    if (item.status === 'running') {
      options.onWarning('该运行仍标记为执行中，请先在原会话暂停，避免并发恢复。');
      return '';
    }
    if (!item.can_resume) {
      options.onWarning(item.status === 'completed' ? '已完成运行保持只读，请在历史中查看或重新下载交付包。' : '该运行没有可恢复的稳定检查点。');
      return '';
    }
    options.cancelInitialRecovery();
    try {
      const snapshot = await getRun(item.run_id);
      const resolution = resolveHistoricalRunOpen(snapshot, item.run_id);
      if (resolution.kind !== 'restore') {
        options.onWarning('该运行的最新状态已不满足恢复条件，请刷新历史后重试。');
        return '';
      }
      options.stopActiveStream();
      await options.onProjectContext(projectIdForRun(snapshot.project_id, item.run_id));
      options.setRunSource('backend');
      if (snapshot.workflow) {
        options.suppressWorkflowSave(snapshot.workflow);
        options.setWorkflow(snapshot.workflow);
      }
      const hydrated = {
        ...resolution.hydrated,
        paused: true,
        runControlState: 'paused' as const,
      };
      await options.onRestore(hydrated, false);
      options.onWarning('');
      return hydrated.selectedId || item.current_stage.id || 'info';
    } catch (error) {
      options.onWarning(`打开历史运行失败：${errorMessage(error)}`);
      return '';
    }
  }, [options]);

  const restoreCheckpoint = useCallback(async (item: RunHistoryItem) => {
    if (options.activeRunId && options.activeRunId !== item.run_id && (options.running || ['starting', 'running', 'stop_requested'].includes(options.runControlState))) {
      options.onWarning('当前运行仍在执行，请先暂停后再恢复其他检查点。');
      return '';
    }
    options.cancelInitialRecovery();
    try {
      const snapshots = await listRunSnapshots(item.run_id);
      if (!snapshots.latest_restorable_snapshot_id) {
        options.onWarning('该运行没有可恢复的稳定检查点。');
        return '';
      }
      await restoreRunSnapshot(item.run_id, {
        snapshot_id: snapshots.latest_restorable_snapshot_id,
        request_id: historyRequestId(item.run_id),
        expected_revision: snapshots.state_revision,
      });
      await options.historyRefresh();
      return openRun({ ...item, status: 'paused', can_resume: true });
    } catch (error) {
      options.onWarning(`恢复检查点失败：${errorMessage(error)}`);
      return '';
    }
  }, [openRun, options]);

  const downloadExport = useCallback(async (item: RunHistoryItem, requestedReceipt?: ExportReceipt) => {
    const receipt = requestedReceipt ?? item.latest_export;
    if (!receipt) {
      options.onWarning('该运行还没有可重新下载的交付记录。');
      return;
    }
    try {
      const downloaded = await downloadRunExportReceipt(item.run_id, receipt.export_id, {
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
      options.onWarning('');
    } catch (error) {
      options.onWarning(`下载历史交付失败：${errorMessage(error)}`);
    }
  }, [options]);

  return { downloadExport, openRun, restoreCheckpoint };
}

function historyRequestId(runId: string) {
  const id = typeof crypto !== 'undefined' && 'randomUUID' in crypto
    ? crypto.randomUUID()
    : `${Date.now()}-${Math.random().toString(16).slice(2)}`;
  return `history-restore-${runId}-${id}`.slice(0, 160);
}

function errorMessage(error: unknown) {
  return error instanceof Error ? error.message : '未知错误';
}
