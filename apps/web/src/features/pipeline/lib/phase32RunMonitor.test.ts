import { describe, expect, it } from "vitest"
import type {
  Phase32CurrentArtifact,
  Phase32RunEvent,
  Phase32RunReadModel,
} from "../contracts/run"
import {
  eventCategory,
  monitorUnitRefs,
  monitorUnitState,
  preferredMonitorUnit,
  projectMonitorArtifact,
} from "./phase32RunMonitor"

describe("phase32RunMonitor", () => {
  it("projects accepted prose as a readable document instead of raw JSON", () => {
    const projection = projectMonitorArtifact(
      artifact("chapter", {
        chapter_ref: "chapter-2",
        content: "第一段。\n\n第二段。",
        pov_subject_ref: "lin",
        title: "回声",
        volume_ref: "volume-1",
      }),
    )

    expect(projection.title).toBe("回声")
    expect(projection.document?.paragraphs).toEqual(["第一段。", "第二段。"])
    expect(projection.fields).toEqual([
      { label: "视角人物", value: "lin", wide: false },
      { label: "所属卷", value: "volume-1", wide: false },
    ])
    expect(JSON.stringify(projection)).not.toContain("chapter_ref")
  })

  it("keeps screenplay block semantics and speaker identity", () => {
    const projection = projectMonitorArtifact(
      artifact("screenplay_draft", {
        blocks: [
          { kind: "scene_heading", text: "内景·档案室·夜" },
          { kind: "dialogue", speaker_ref: "maya", text: "这份签名被替换过。" },
        ],
        scene_ref: "scene-2",
      }),
    )

    expect(projection.document?.title).toBe("scene-2")
    expect(projection.document?.blocks[1]).toEqual({
      kind: "dialogue",
      speaker: "maya",
      text: "这份签名被替换过。",
    })
  })

  it("derives unit selection and state from the canonical read model", () => {
    const readModel = runReadModel()

    expect(monitorUnitRefs(readModel, "text")).toEqual([
      "chapter-1",
      "chapter-2",
      "chapter-3",
    ])
    expect(
      preferredMonitorUnit(readModel, "text", readModel.pending_decisions),
    ).toBe("chapter-2")
    expect(monitorUnitState(readModel, "text", "chapter-1")).toBe("committed")
    expect(monitorUnitState(readModel, "text", "chapter-2")).toBe("active")
    expect(monitorUnitState(readModel, "text", "chapter-3")).toBe("failed")
  })

  it("classifies formal evidence, writeback, checkpoint and failure events", () => {
    expect(eventCategory(event("evidence.completed"))).toBe("evidence")
    expect(eventCategory(event("writeback.committed"))).toBe("writeback")
    expect(eventCategory(event("checkpoint.saved"))).toBe("checkpoint")
    expect(eventCategory(event("run.branched"))).toBe("lifecycle")
    expect(eventCategory(event("unit.failed"))).toBe("failure")
  })
})

function artifact(
  artifactKind: string,
  payload: Record<string, unknown>,
): Phase32CurrentArtifact {
  return {
    artifact_kind: artifactKind,
    artifact_ref: "artifact-1",
    creation_route_id: "long_novel",
    editable: false,
    payload,
    payload_digest: "a".repeat(64),
    pending_decision: null,
    run_id: "run-1",
    stage_id: artifactKind === "chapter" ? "text" : "script",
    status: "committed",
    unit_ref: artifactKind === "chapter" ? "chapter-2" : "scene-2",
  }
}

function runReadModel(): Phase32RunReadModel {
  return {
    active_stage_id: "text",
    active_unit_ref: "chapter-2",
    failure: {
      code: "provider_timeout",
      message: "第三章生成超时",
      retryable: true,
      stage_id: "text",
      unit_ref: "chapter-3",
    },
    pending_decisions: [],
    sequential_stage_progress: {
      text: {
        committed_artifact_refs: { "chapter-1": "artifact-chapter-1" },
        ordered_unit_refs: ["chapter-1", "chapter-2", "chapter-3"],
      },
    },
  } as unknown as Phase32RunReadModel
}

function event(type: string) {
  return { type } as Phase32RunEvent
}
