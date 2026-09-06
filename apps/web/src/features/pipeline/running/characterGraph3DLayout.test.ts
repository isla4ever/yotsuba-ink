import { describe, expect, it } from "vitest"
import { projectCharacterGraph } from "../lib/characterGraph"
import {
  characterCameraFrame,
  initialCharacterLayout,
} from "./characterGraph3DLayout"
import { relationCurve } from "./characterGraph3DObjects"

describe("Phase 32 character graph projection", () => {
  it("builds a finite deterministic layout without writing coordinates into Cast", () => {
    const artifact = {
      characters: [
        {
          subject_ref: "maya",
          display_name: "玛雅",
          role: "档案记者",
          desire: "查清真相",
          stakes: "失去职业",
          constraints: ["不能公开未核实证据"],
          voice: "短句",
          arc_scope: "承担公开代价",
        },
        {
          subject_ref: "lin",
          display_name: "林岚",
          role: "档案馆员",
          desire: "保住原件",
          stakes: "暴露过去的沉默",
          constraints: ["不能带走原件"],
          voice: "谨慎",
          arc_scope: "成为有限证人",
        },
      ],
      relationships: [
        {
          from_subject_ref: "maya",
          to_subject_ref: "lin",
          pressure: "公开时机存在分歧",
          change_trigger: "出现保护证人的方案",
        },
      ],
    }
    const graph = projectCharacterGraph(artifact)
    const nodes = initialCharacterLayout(graph.nodes, false)
    const frame = characterCameraFrame(nodes, 720, 480)

    expect(nodes[0].tier).toBe("anchor")
    expect(Number.isFinite(frame.distance)).toBe(true)
    expect(relationCurve(graph.links[0])).toBeGreaterThan(0)
    expect(artifact.characters[0]).not.toHaveProperty("x")
  })
})
