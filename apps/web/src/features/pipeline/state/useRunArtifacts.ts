import { useEffect, useMemo, useState } from "react"
import type {
  ChapterVersionRecord,
  GraphRunEnvelope,
  NarrativeStageId,
  RunArtifactRecord,
} from "../contracts/run"
import { getArtifactRecord, getRunChapters } from "../services/runApi"

export function useRunArtifacts(
  envelope: GraphRunEnvelope | null,
  chapterRefreshKey = 0,
) {
  const [artifacts, setArtifacts] =
    useState<Partial<Record<NarrativeStageId, RunArtifactRecord>>>({})
  const [candidateArtifacts, setCandidateArtifacts] =
    useState<Partial<Record<NarrativeStageId, RunArtifactRecord>>>({})
  const [chapters, setChapters] = useState<ChapterVersionRecord[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState("")
  const runId = envelope?.definition.run_id ?? ""
  const artifactSignature = JSON.stringify(
    envelope?.read_model.artifact_refs ?? {},
  )
  const candidateSignature = JSON.stringify(
    envelope?.read_model.pending_decisions.map((decision) => ({
      artifact_ref: decision.artifact_ref,
      node_id: decision.node_id,
      type: decision.type,
    })) ?? [],
  )

  useEffect(() => {
    setArtifacts({})
    setCandidateArtifacts({})
    setChapters([])
    setError("")
    if (!runId || !envelope) {
      setLoading(false)
      return undefined
    }
    const controller = new AbortController()
    setLoading(true)
    const load = async () => {
      try {
        const refs = Object.entries(
          envelope.read_model.artifact_refs,
        ) as Array<[NarrativeStageId, string]>
        const records = await Promise.all(
          refs.map(
            async ([stageId, artifactId]) =>
              [
                stageId,
                await getArtifactRecord(runId, artifactId, controller.signal),
              ] as const,
          ),
        )
        const candidateRefs = envelope.read_model.pending_decisions.flatMap(
          (decision) => {
            const nodeId =
              typeof decision.node_id === "string" ? decision.node_id : ""
            const artifactRef =
              typeof decision.artifact_ref === "string"
                ? decision.artifact_ref
                : ""
            const stageId = nodeId.split(".")[0] as NarrativeStageId
            return decision.type === "stage_artifact_decision" && artifactRef
              ? [[stageId, artifactRef] as const]
              : []
          },
        )
        const candidateRecords = await Promise.all(
          candidateRefs.map(
            async ([stageId, artifactId]) =>
              [
                stageId,
                await getArtifactRecord(runId, artifactId, controller.signal),
              ] as const,
          ),
        )
        const chapterRecords = await getRunChapters(runId, controller.signal)
        setArtifacts(Object.fromEntries(records))
        setCandidateArtifacts(Object.fromEntries(candidateRecords))
        setChapters(chapterRecords)
        setError("")
      } catch (reason) {
        if (controller.signal.aborted) return
        setError(reason instanceof Error ? reason.message : "Run 产物读取失败")
      } finally {
        if (!controller.signal.aborted) setLoading(false)
      }
    }
    void load()
    return () => controller.abort()
  }, [artifactSignature, candidateSignature, chapterRefreshKey, runId])

  const acceptedChapters = useMemo(
    () =>
      chapters.filter(
        (chapter) => chapter.artifact.author_status === "accepted",
      ),
    [chapters],
  )

  return {
    acceptedChapters,
    artifacts,
    candidateArtifacts,
    chapters,
    error,
    loading,
  }
}
