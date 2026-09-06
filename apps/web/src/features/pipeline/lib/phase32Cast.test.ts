import { describe, expect, it } from "vitest"
import { castDiagnostics, parsePhase32Cast } from "./phase32Cast"

describe("phase32Cast", () => {
  it("parses the CharacterBibleAggregate and derives relationship diagnostics", () => {
    const parsed = parsePhase32Cast(castPayload())
    expect(parsed.error).toBe("")
    expect(parsed.artifact?.characters.map((item) => item.subject_ref)).toEqual(
      ["maya", "lin"],
    )
    const diagnostics = castDiagnostics(parsed.artifact!)
    expect(diagnostics.relationshipCount).toBe(1)
    expect(diagnostics.relationshipDegree.get("maya")).toBe(1)
    expect(diagnostics.isolatedSubjectRefs).toEqual([])
  })

  it("keeps the aggregate renderable while surfacing dangling relationship refs", () => {
    const payload = castPayload()
    payload.relationships[0].to_subject_ref = "unknown"
    const parsed = parsePhase32Cast(payload)
    expect(parsed.artifact).not.toBeNull()
    expect(parsed.error).toContain("未知")
  })

  it("rejects generic JSON shapes instead of guessing old Character Bible fields", () => {
    const parsed = parsePhase32Cast({ subjects: [], relations: [] })
    expect(parsed.artifact).toBeNull()
    expect(parsed.error).toContain("未知字段")
  })
})

function castPayload() {
  return {
    characters: [
      {
        subject_ref: "maya",
        display_name: "玛雅",
        role: "追查被删改档案的记者",
        desire: "在听证前找出原始签名链",
        stakes: "失去职业与家人的信任",
        constraints: ["不能公开未经核实的证据"],
        voice: "短句，先核对事实再表达",
        arc_scope: "从旁观者转为承担公开代价的人",
      },
      {
        subject_ref: "lin",
        display_name: "林岚",
        role: "掌握档案入口的前同事",
        desire: "保住档案馆与自己的职位",
        stakes: "协助调查会暴露过去的沉默",
        constraints: ["无法直接带走原件"],
        voice: "回避主语，用程序语言保护自己",
        arc_scope: "从阻拦者转为有限证人",
      },
    ],
    relationships: [
      {
        from_subject_ref: "maya",
        to_subject_ref: "lin",
        pressure: "玛雅需要入口，林岚害怕再次卷入调查。",
        change_trigger: "玛雅拿出能保护档案馆而非摧毁它的公开方案。",
      },
    ],
  }
}
