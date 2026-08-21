import { useEffect, useState } from "react"
import type { KnowledgeDocument } from "../contracts/knowledge"
import { listKnowledgeDocuments } from "../services/knowledgeApi"

export function useProjectKnowledge(projectId: string, enabled: boolean) {
  const [documents, setDocuments] = useState<KnowledgeDocument[]>([])
  const [error, setError] = useState("")
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    setDocuments([])
    setError("")
    if (!enabled || !projectId) return undefined
    const controller = new AbortController()
    setLoading(true)
    void listKnowledgeDocuments(projectId, controller.signal)
      .then((records) => {
        setDocuments(records)
        setError("")
      })
      .catch((reason: unknown) => {
        if (!controller.signal.aborted)
          setError(
            reason instanceof Error ? reason.message : "知识库读取失败",
          )
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false)
      })
    return () => controller.abort()
  }, [enabled, projectId])

  return { documents, error, loading }
}
