import { useCallback, useEffect, useMemo, useState } from "react"
import type { CreationWorkflowCatalogItem } from "../contracts/creationWizard"
import { listCreationWorkflowCatalog } from "../services/creationCatalogApi"

const ROUTE_ORDER = ["screenplay_sample", "short_novel", "long_novel"]

export function useWorkflowTemplates() {
  const [workflows, setWorkflows] = useState<CreationWorkflowCatalogItem[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState("")

  const refresh = useCallback(async (signal?: AbortSignal) => {
    setLoading(true)
    try {
      const loaded = await listCreationWorkflowCatalog(signal)
      setWorkflows(
        loaded
          .filter((workflow) => workflow.available)
          .sort(
            (left, right) =>
              ROUTE_ORDER.indexOf(left.routeId) -
                ROUTE_ORDER.indexOf(right.routeId) ||
              Number(right.source === "official") -
                Number(left.source === "official") ||
              left.name.localeCompare(right.name, "zh-CN"),
          ),
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

  return useMemo(
    () => ({ error, loading, refresh, workflows }),
    [error, loading, refresh, workflows],
  )
}
