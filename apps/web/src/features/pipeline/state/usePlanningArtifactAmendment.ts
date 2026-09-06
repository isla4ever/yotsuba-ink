import { useCallback } from "react"
import type { Phase32CurrentArtifact } from "../contracts/run"
import { isProductionStageRoute } from "../lib/routes"
import { useApp } from "./PipelineAppProvider"
import { useArtifactAmendment } from "./useArtifactAmendment"

export function usePlanningArtifactAmendment(
  stageId: string,
  current: Phase32CurrentArtifact | null,
) {
  const { activeRun, openProject, refreshActiveProject, refreshRun } = useApp()
  const flow = useArtifactAmendment({
    run: activeRun,
    stageId,
    current,
    onSourceRunChanged: refreshRun,
  })

  const enterSuccessor = useCallback(async () => {
    const receipt = flow.branchReceipt
    const targetRun = flow.targetRun
    if (!receipt || !targetRun) throw new Error("Successor Run 回执尚未就绪")
    if (!isProductionStageRoute(receipt.frontier_stage_id))
      throw new Error("Successor frontier 不属于当前生产路线")
    const project = await refreshActiveProject()
    if (!project || project.latestRunId !== receipt.target_run_id)
      throw new Error(
        "项目最新 Run 与 successor receipt 不一致，请重新恢复分支",
      )
    if (targetRun.definition.run_id !== project.latestRunId)
      throw new Error("Successor Run 身份与项目 lineage 不一致")
    openProject(project, receipt.frontier_stage_id)
  }, [flow.branchReceipt, flow.targetRun, openProject, refreshActiveProject])

  return { enterSuccessor, flow }
}
