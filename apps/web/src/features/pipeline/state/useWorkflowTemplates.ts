import { useCallback, useEffect, useMemo, useState } from "react"
import type { WorkflowDefinition } from "../contracts/workflow"
import { workflowSort } from "../lib/workflowPresentation"
import {
  deleteWorkflowDefinition,
  listWorkflowDefinitions,
} from "../services/workflowApi"

export function useWorkflowTemplates() {
  const [workflows, setWorkflows] = useState<WorkflowDefinition[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState("")

  const refresh = useCallback(async (signal?: AbortSignal) => {
    setLoading(true)
    try {
      const loaded = await listWorkflowDefinitions(signal)
      setWorkflows(
        loaded.filter((workflow) => workflow.is_template).sort(workflowSort),
      )
      setError("")
    } catch (reason) {
      if (signal?.aborted) return
      setError(
        reason instanceof Error ? reason.message : "工作流模板暂时不可用",
      )
    } finally {
      if (!signal?.aborted) setLoading(false)
    }
  }, [])

  useEffect(() => {
    const controller = new AbortController()
    void refresh(controller.signal)
    return () => controller.abort()
  }, [refresh])

  const remove = useCallback(async (workflowId: string) => {
    try {
      await deleteWorkflowDefinition(workflowId)
      setWorkflows((current) =>
        current.filter((workflow) => workflow.id !== workflowId),
      )
      setError("")
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "删除工作流失败")
    }
  }, [])

  return useMemo(
    () => ({ error, loading, refresh, remove, workflows }),
    [error, loading, refresh, remove, workflows],
  )
}
