import { useCallback, useEffect, useMemo, useState } from "react"
import type { Project } from "@/features/pipeline/contracts/app"
import type { ProjectRecord, ProjectSummary } from "../contracts/project"
import { projectPresentation } from "../lib/projectPresentation"
import {
  getProjectSummaries,
  listProjects,
  reorderProjects,
} from "../services/projectApi"

export function useStudioProjects() {
  const [records, setRecords] = useState<ProjectRecord[]>([])
  const [summaries, setSummaries] = useState<Record<string, ProjectSummary>>({})
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState("")

  const refresh = useCallback(async (signal?: AbortSignal) => {
    setLoading(true)
    try {
      const projects = await listProjects(signal)
      setRecords(projects)
      setError("")
      setSummaries(await getProjectSummaries(projects, signal))
    } catch (reason) {
      if (signal?.aborted) return
      setError(reason instanceof Error ? reason.message : "作品库暂时不可用")
    } finally {
      if (!signal?.aborted) setLoading(false)
    }
  }, [])

  useEffect(() => {
    const controller = new AbortController()
    void refresh(controller.signal)
    return () => controller.abort()
  }, [refresh])

  const projects = useMemo(
    () =>
      records.map((project) =>
        projectPresentation(project, summaries[project.id]),
      ),
    [records, summaries],
  )

  const reorder = useCallback(
    async (next: Project[]) => {
      const previous = records
      setRecords(
        next
          .map((item) => records.find((record) => record.id === item.id))
          .filter(Boolean) as ProjectRecord[],
      )
      try {
        setRecords(await reorderProjects(next.map((item) => item.id)))
        setError("")
      } catch (reason) {
        setRecords(previous)
        setError(reason instanceof Error ? reason.message : "作品排序保存失败")
      }
    },
    [records],
  )

  return { error, loading, projects, refresh, reorder }
}
