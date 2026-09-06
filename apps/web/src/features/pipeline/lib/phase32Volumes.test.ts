import { describe, expect, it } from "vitest"
import {
  extractVolumeReferenceContext,
  parsePhase32Volumes,
  reorderVolumeContracts,
  volumeArchitectureDiagnostics,
} from "./phase32Volumes"

describe("Phase 32 Volume Architecture contract", () => {
  it("parses the aggregate and projects Part and Cast coverage", () => {
    const parsed = parsePhase32Volumes(volumePayload())

    expect(parsed.error).toBe("")
    expect(parsed.artifact?.volumes.map((volume) => volume.volume_ref)).toEqual(
      ["volume-1", "volume-2"],
    )
    expect(volumeArchitectureDiagnostics(parsed.artifact!)).toEqual({
      partCoverage: [
        { partRef: "part-1", volumeRefs: ["volume-1"], lengthHint: 40_000 },
        {
          partRef: "part-2",
          volumeRefs: ["volume-2"],
          lengthHint: 55_000,
        },
      ],
      totalLengthHint: 95_000,
      uniqueCastCount: 2,
      volumeCount: 2,
    })
  })

  it("reorders stable Volume refs and rebuilds contiguous ordinals", () => {
    const volumes = parsePhase32Volumes(volumePayload()).artifact!.volumes
    const reordered = reorderVolumeContracts(volumes, 0, 1)

    expect(reordered.map((volume) => volume.volume_ref)).toEqual([
      "volume-2",
      "volume-1",
    ])
    expect(reordered.map((volume) => volume.ordinal)).toEqual([1, 2])
    expect(reordered[0].part_ref).toBe("part-2")
  })

  it("keeps the draft readable while reporting duplicate refs and invalid soft length", () => {
    const payload = volumePayload()
    payload.volumes[1].volume_ref = "volume-1"
    payload.volumes[1].length_hint = 400

    const parsed = parsePhase32Volumes(payload)
    expect(parsed.artifact).not.toBeNull()
    expect(parsed.error).toContain("重复卷")
  })

  it("extracts human-readable labels from committed Part and Cast artifacts", () => {
    const context = extractVolumeReferenceContext(
      {
        parts: [
          {
            part_ref: "part-1",
            dramatic_question: "她是否愿意公开自己的违规取证？",
          },
        ],
      },
      { characters: [{ subject_ref: "maya", display_name: "玛雅" }] },
    )

    expect(context.parts["part-1"].label).toContain("Part 01")
    expect(context.cast.maya.label).toBe("玛雅")
  })
})

function volumePayload() {
  return {
    volumes: [
      {
        volume_ref: "volume-1",
        ordinal: 1,
        part_ref: "part-1",
        promise: "找到第一份原始档案。",
        conflict: "机构试图销毁备份。",
        climax: "主角在听证会上提交证据。",
        closure: "调查进入公众视野。",
        cast_subject_refs: ["maya"],
        length_hint: 40_000,
      },
      {
        volume_ref: "volume-2",
        ordinal: 2,
        part_ref: "part-2",
        promise: "把证据推进为可公开核验的签名链。",
        conflict: "证人安全与公开时限冲突。",
        climax: "主角公开自己的违规取证。",
        closure: "事实进入公共记录。",
        cast_subject_refs: ["maya", "liang"],
        length_hint: 55_000,
      },
    ],
  }
}
