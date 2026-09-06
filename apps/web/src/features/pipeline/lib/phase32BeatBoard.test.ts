import { describe, expect, it } from "vitest"
import {
  beatBoardDiagnostics,
  extractBeatBoardReferenceContext,
  normalizeBeatBoardReferences,
  parsePhase32BeatBoard,
  reorderBeatBoardBeats,
} from "./phase32BeatBoard"

describe("Phase 32 Beat Board contract", () => {
  it("parses decision beats and projects setup/payoff coverage", () => {
    const parsed = parsePhase32BeatBoard(beatBoardPayload())

    expect(parsed.error).toBe("")
    expect(parsed.artifact?.beats.map((beat) => beat.beat_ref)).toEqual([
      "beat-1",
      "beat-2",
    ])
    expect(beatBoardDiagnostics(parsed.artifact!)).toEqual({
      beatCount: 2,
      beatsWithoutReference: [],
      referenceCoverage: [
        {
          beatRefs: ["beat-1", "beat-2"],
          reference: "setup-signature-chain",
        },
        { beatRefs: ["beat-2"], reference: "payoff-public-record" },
      ],
      uniqueReferenceCount: 2,
    })
  })

  it("reorders beats without changing frozen refs", () => {
    const beats = parsePhase32BeatBoard(beatBoardPayload()).artifact!.beats
    const reordered = reorderBeatBoardBeats(beats, 0, 1)

    expect(reordered.map((beat) => beat.beat_ref)).toEqual(["beat-2", "beat-1"])
  })

  it("keeps malformed drafts visible while reporting contract drift", () => {
    const payload = beatBoardPayload()
    payload.beats[1].beat_ref = "beat-1"
    payload.beats[1].character_decision = ""

    const parsed = parsePhase32BeatBoard(payload)
    expect(parsed.artifact).not.toBeNull()
    expect(parsed.error).toContain("重复身份")
  })

  it("extracts the Brief promise and upstream Cast without inventing beat links", () => {
    const context = extractBeatBoardReferenceContext(
      {
        audience_promise: "证据驱动的调查样片",
        ending_effect: "签名页在听证会上重新拼合",
        sample_type: "调查悬疑样片",
        target_minutes: 12,
        tone: "冷峻克制",
        visible_conflict: "闭馆前证明签名页被替换",
      },
      {
        characters: [
          { subject_ref: "maya", display_name: "玛雅", role: "档案记者" },
        ],
      },
    )

    expect(context.brief.targetMinutes).toBe(12)
    expect(context.cast.maya).toEqual({
      label: "玛雅",
      ref: "maya",
      role: "档案记者",
    })
  })

  it("normalizes comma and line separated stable references", () => {
    expect(
      normalizeBeatBoardReferences(
        "setup-signature-chain， payoff-public-record\nsetup-signature-chain",
      ),
    ).toEqual(["setup-signature-chain", "payoff-public-record"])
  })
})

export function beatBoardPayload() {
  return {
    beats: [
      {
        beat_ref: "beat-1",
        dramatic_job: "迫使主角越权查档。",
        visible_pressure: "档案室即将关闭。",
        character_decision: "主角复制未授权记录。",
        outcome: "她留下可追查的证据。",
        setup_or_payoff_refs: ["setup-signature-chain"],
        timing_hint: "约 90 秒",
      },
      {
        beat_ref: "beat-2",
        dramatic_job: "让越权调查转化为公开风险。",
        visible_pressure: "保安封锁出口。",
        character_decision: "主角拒绝交出原件。",
        outcome: "证据进入公开记录。",
        setup_or_payoff_refs: ["setup-signature-chain", "payoff-public-record"],
        timing_hint: "约 120 秒",
      },
    ],
  }
}
