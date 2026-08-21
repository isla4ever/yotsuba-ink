import { useCallback, useEffect, useState } from "react"
import type { ExportArtifact } from "../contracts/delivery"
import type { ExportReceipt } from "../contracts/runHistory"
import {
  downloadRunExportReceipt,
  listRunExports,
} from "../services/runHistoryApi"

type DeliveryStatus =
  | "idle"
  | "loading"
  | "ready"
  | "missing"
  | "error"
  | "downloading"

type DeliveryState = {
  error: string
  receipt: ExportReceipt | null
  status: DeliveryStatus
}

export function useExportDelivery(
  runId: string,
  artifact: ExportArtifact | null,
  enabled: boolean,
  revision: string,
) {
  const [state, setState] = useState<DeliveryState>({
    error: "",
    receipt: null,
    status: "idle",
  })

  useEffect(() => {
    if (!enabled || !runId || !artifact) {
      setState({ error: "", receipt: null, status: "idle" })
      return undefined
    }
    const controller = new AbortController()
    setState({ error: "", receipt: null, status: "loading" })
    void listRunExports(runId, controller.signal)
      .then((receipts) => {
        const receipt =
          receipts.find((item) => receiptMatchesArtifact(item, artifact)) ??
          null
        setState({
          error: "",
          receipt,
          status: receipt ? "ready" : "missing",
        })
      })
      .catch((reason) => {
        if (controller.signal.aborted) return
        setState({
          error:
            reason instanceof Error ? reason.message : "导出回执读取失败",
          receipt: null,
          status: "error",
        })
      })
    return () => controller.abort()
  }, [artifact, enabled, revision, runId])

  const download = useCallback(async () => {
    if (!state.receipt) return
    const receipt = state.receipt
    setState({ error: "", receipt, status: "downloading" })
    try {
      const downloaded = await downloadRunExportReceipt(
        runId,
        receipt.export_id,
        {
          expectedSha256: receipt.sha256,
          expectedSizeBytes: receipt.size_bytes,
        },
      )
      const url = URL.createObjectURL(downloaded.blob)
      const anchor = document.createElement("a")
      anchor.href = url
      anchor.download = downloaded.filename
      document.body.appendChild(anchor)
      anchor.click()
      anchor.remove()
      window.setTimeout(() => URL.revokeObjectURL(url), 0)
      setState({ error: "", receipt, status: "ready" })
    } catch (reason) {
      setState({
        error: reason instanceof Error ? reason.message : "导出文件下载失败",
        receipt,
        status: "error",
      })
    }
  }, [runId, state.receipt])

  return { ...state, download }
}

function receiptMatchesArtifact(
  receipt: ExportReceipt,
  artifact: ExportArtifact,
) {
  return (
    receipt.format === artifact.format &&
    receipt.cover_asset_id === artifact.cover_asset_id &&
    equalStrings(receipt.chapter_version_ids, artifact.chapter_version_ids) &&
    receipt.metadata.title === artifact.metadata.title &&
    receipt.metadata.author === artifact.metadata.author &&
    receipt.metadata.version_note === artifact.metadata.version_note
  )
}

function equalStrings(left: string[], right: string[]) {
  return (
    left.length === right.length &&
    left.every((value, index) => value === right[index])
  )
}
