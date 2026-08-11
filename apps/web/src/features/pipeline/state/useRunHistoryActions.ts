import { useCallback } from 'react';
import type { ExportReceipt, RunControlState, RunHistoryItem } from '../contracts';
import { createRunBranch, getRun } from '../services/runApi';
import {
  downloadRunExportReceipt,
} from '../services/runHistoryApi';
import type { RunSource } from '../lib/runSource';
import { resolveServerRunRecovery, type HydratedRunState } from './runState';

type Options = {
  activeRunId: string;
  cancelInitialRecovery: () => void;
  historyRefresh: () => Promise<void>;
  /** Switch the shell to the project that owns the new LangGraph branch. */
  onProjectContext: (projectId: string) => Promise<void>;
  onRestore: (hydrated: HydratedRunState, reconnect: boolean) => Promise<void>;
  onWarning: (message: string) => void;
  runControlState: RunControlState;
  running: boolean;
  setRunSource: (source: RunSource) => void;
  stopActiveStream: () => void;
};

export function useRunHistoryActions(options: Options) {
  const restoreProjectRun = useCallback(async (item: RunHistoryItem) => {
    if (options.activeRunId && options.activeRunId !== item.run_id && (options.running || ['starting', 'running', 'stop_requested'].includes(options.runControlState))) {
      options.onWarning('当前运行仍在执行，请等待进入人工决策点或完成后再切换作品。');
      return '';
    }
    options.cancelInitialRecovery();
    try {
      const source = await getRun(item.run_id);
      const resolution = resolveServerRunRecovery(source, item.run_id);
      if (resolution.kind !== 'restore') {
        options.onWarning('该作品的最新运行没有可恢复的 LangGraph 状态。');
        return '';
      }
      options.stopActiveStream();
      await options.onProjectContext(source.definition.project_id);
      options.setRunSource('backend');
      void options.onRestore(resolution.hydrated, resolution.reconnect);
      options.onWarning('');
      return resolution.hydrated.selectedId || item.current_stage.id || 'info';
    } catch (error) {
      options.onWarning(`恢复作品运行失败：${errorMessage(error)}`);
      return '';
    }
  }, [options]);

  const openRun = useCallback(async (item: RunHistoryItem) => {
    if (item.run_id === options.activeRunId) {
      try {
        const envelope = await getRun(item.run_id);
        options.onWarning('');
        return envelope.read_model.active_stage_id;
      } catch (error) {
        options.onWarning(`读取当前运行配置失败：${errorMessage(error)}`);
        return '';
      }
    }
    if (options.activeRunId && (options.running || ['starting', 'running', 'stop_requested'].includes(options.runControlState))) {
      options.onWarning('当前运行仍在执行，请等待进入人工决策点或完成后再切换创作历史。');
      return '';
    }
    if (item.status === 'running') {
      options.onWarning('该运行仍标记为执行中，请从原会话继续观察，避免并发恢复。');
      return '';
    }
    if (!item.can_branch) {
      options.onWarning(item.status === 'completed' ? '已完成运行保持只读，请在历史中查看或重新下载交付包。' : '该运行没有可创建分支的人工决策检查点。');
      return '';
    }
    options.cancelInitialRecovery();
    try {
      const source = await getRun(item.run_id);
      if (
        source.read_model.status !== 'awaiting_decision'
        || !source.read_model.checkpoint_id
        || !source.read_model.pending_decisions.length
      ) {
        options.onWarning('该运行不在可分支的 LangGraph 决策检查点。');
        return '';
      }
      const targetRunId = branchRunId();
      await createRunBranch(
        item.run_id,
        source.read_model.checkpoint_id,
        targetRunId,
      );
      const branch = await getRun(targetRunId);
      const resolution = resolveServerRunRecovery(branch, targetRunId);
      if (resolution.kind !== 'restore') {
        options.onWarning('新分支没有形成可恢复的 LangGraph 决策状态。');
        return '';
      }
      options.stopActiveStream();
      await options.onProjectContext(branch.definition.project_id);
      options.setRunSource('backend');
      const hydrated = resolution.hydrated;
      void options.onRestore(hydrated, resolution.reconnect);
      options.onWarning('');
      return hydrated.selectedId || item.current_stage.id || 'info';
    } catch (error) {
      options.onWarning(`打开历史运行失败：${errorMessage(error)}`);
      return '';
    }
  }, [options]);

  const branchFromCheckpoint = useCallback(async (item: RunHistoryItem) => {
    if (options.activeRunId && options.activeRunId !== item.run_id && (options.running || ['starting', 'running', 'stop_requested'].includes(options.runControlState))) {
      options.onWarning('当前运行仍在执行，请等待当前操作结束后再创建检查点分支。');
      return '';
    }
    try {
      const stageId = await openRun(item);
      if (stageId) await options.historyRefresh();
      return stageId;
    } catch (error) {
      options.onWarning(`创建检查点分支失败：${errorMessage(error)}`);
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

  return { branchFromCheckpoint, downloadExport, openRun, restoreProjectRun };
}

function branchRunId() {
  const id = typeof crypto !== 'undefined' && 'randomUUID' in crypto
    ? crypto.randomUUID()
    : `${Date.now()}-${Math.random().toString(16).slice(2)}`;
  return `run-${id}`.slice(0, 160);
}

function errorMessage(error: unknown) {
  return error instanceof Error ? error.message : '未知错误';
}
