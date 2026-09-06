import { describe, expect, it } from "vitest"
import {
  extractSectionPlanReferenceContext,
  parsePhase32SectionPlan,
  reorderSectionPlanUnits,
  sectionPlanDiagnostics,
} from "./phase32SectionPlan"

describe("Phase 32 Section Plan contract", () => {
  it("parses ordered writing units and projects budget and promise coverage", () => {
    const parsed = parsePhase32SectionPlan(sectionPlanPayload())

    expect(parsed.error).toBe("")
    expect(parsed.artifact?.units.map((unit) => unit.unit_ref)).toEqual([
      "unit-1",
      "unit-2",
    ])
    expect(sectionPlanDiagnostics(parsed.artifact!)).toEqual({
      promiseCoverage: [
        {
          promiseRef: "promise-truth-cost",
          unitRefs: ["unit-1", "unit-2"],
        },
        { promiseRef: "promise-public-record", unitRefs: ["unit-2"] },
      ],
      totalCharacterBudget: 7_000,
      uniquePovCount: 2,
      unitCount: 2,
      unitsWithoutPromise: [],
    })
  })

  it("reorders stable unit refs and rebuilds contiguous ordinals", () => {
    const units = parsePhase32SectionPlan(sectionPlanPayload()).artifact!.units
    const reordered = reorderSectionPlanUnits(units, 0, 1)

    expect(reordered.map((unit) => unit.unit_ref)).toEqual(["unit-2", "unit-1"])
    expect(reordered.map((unit) => unit.ordinal)).toEqual([1, 2])
  })

  it("keeps malformed drafts readable while reporting reference drift", () => {
    const payload = sectionPlanPayload()
    payload.units[1].unit_ref = "unit-1"
    payload.units[1].soft_character_budget = 20

    const parsed = parsePhase32SectionPlan(payload)
    expect(parsed.artifact).not.toBeNull()
    expect(parsed.error).toContain("重复单元")
  })

  it("extracts Cast labels and Story Map promise origins", () => {
    const context = extractSectionPlanReferenceContext(
      {
        anchors: [
          {
            anchor_ref: "anchor-1",
            dramatic_job: "让主角获得第一条可核验证据。",
            promise_refs: ["promise-truth-cost"],
          },
        ],
      },
      { characters: [{ subject_ref: "maya", display_name: "玛雅" }] },
    )

    expect(context.cast.maya.label).toBe("玛雅")
    expect(context.promises["promise-truth-cost"].anchorRefs).toEqual([
      "anchor-1",
    ])
    expect(context.promises["promise-truth-cost"].labels[0]).toContain("证据")
  })
})

export function sectionPlanPayload() {
  return {
    units: [
      {
        unit_ref: "unit-1",
        ordinal: 1,
        title: "封存前的签名",
        dramatic_job: "让主角获得第一条可独立核验的签名证据。",
        pov_subject_ref: "maya",
        scene_load: "档案室核验与走廊拦截。",
        handoff: "签名日期与封存命令发生冲突。",
        soft_character_budget: 3_000,
        promise_refs: ["promise-truth-cost"],
      },
      {
        unit_ref: "unit-2",
        ordinal: 2,
        title: "公开记录",
        dramatic_job: "迫使机构对签名链作出公开回应。",
        pov_subject_ref: "liang",
        scene_load: "听证准备、证人犹豫与公开质询。",
        handoff: "证据进入公共记录，主角承担职业代价。",
        soft_character_budget: 4_000,
        promise_refs: ["promise-truth-cost", "promise-public-record"],
      },
    ],
  }
}
