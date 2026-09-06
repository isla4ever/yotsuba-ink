import { describe, expect, it } from "vitest"
import {
  extractScreenplayReferenceContext,
  parsePhase32Screenplay,
  screenplayContractError,
  screenplayDiagnostics,
  shortSceneRef,
} from "./phase32Screenplay"

describe("phase32Screenplay", () => {
  it("parses a screenplay scene and verifies its frozen Scene Deck contract", () => {
    const parsed = parsePhase32Screenplay(screenplayPayload())
    const context = extractScreenplayReferenceContext(
      sceneDeckPayload(),
      castPayload(),
    )

    expect(parsed.error).toBe("")
    expect(screenplayContractError(parsed.artifact, context)).toBe("")
    expect(screenplayDiagnostics(parsed.artifact!, context)).toMatchObject({
      actionBlocks: 1,
      blockCount: 3,
      dialogueBlocks: 1,
      outOfSceneSpeakerRefs: [],
      sceneHeadingMatches: true,
      sceneKnown: true,
      speakerRefs: ["maya"],
      unknownSpeakerRefs: [],
    })
    expect(shortSceneRef("scene_archive_room")).toBe("SCENE archive room")
  })

  it("rejects malformed block structure before an author can confirm it", () => {
    const missingHeading = screenplayPayload()
    missingHeading.blocks[0] = { kind: "action", text: "灯灭了。" }
    expect(parsePhase32Screenplay(missingHeading).error).toContain("场景标题")

    const missingSpeaker = screenplayPayload()
    delete missingSpeaker.blocks[2].speaker_ref
    expect(parsePhase32Screenplay(missingSpeaker).error).toContain(
      "绑定已确认人物",
    )
  })

  it("surfaces heading drift and speakers outside the frozen Scene cast", () => {
    const context = extractScreenplayReferenceContext(
      sceneDeckPayload(),
      castPayload(),
    )
    const wrongHeading = parsePhase32Screenplay({
      ...screenplayPayload(),
      blocks: [
        { kind: "scene_heading", text: "EXT. 广场 - DAY" },
        { kind: "action", text: "玛雅停下。" },
      ],
    }).artifact
    expect(screenplayContractError(wrongHeading, context)).toContain(
      "Scene Deck",
    )

    const outsideCast = parsePhase32Screenplay({
      ...screenplayPayload(),
      blocks: [
        screenplayPayload().blocks[0],
        { kind: "dialogue", speaker_ref: "guard", text: "现在离开。" },
      ],
    }).artifact
    expect(screenplayContractError(outsideCast, context)).toContain(
      "冻结人物范围",
    )
  })
})

function screenplayPayload() {
  return {
    scene_ref: "scene-1",
    blocks: [
      { kind: "scene_heading", text: "INT. 市档案馆 - NIGHT" },
      { kind: "action", text: "玛雅在熄灯前翻开档案盒。" },
      { kind: "dialogue", speaker_ref: "maya", text: "签名页被换过。" },
    ],
  }
}

function sceneDeckPayload() {
  return {
    scenes: [
      {
        scene_ref: "scene-1",
        heading: "INT. 市档案馆 - NIGHT",
        location_and_time: "闭馆前十分钟",
        cast_subject_refs: ["maya"],
        visible_goal: "找到被替换的签名页。",
        opposition: "保安要求她立即离开。",
        outcome: "她取得带水印的复印件。",
        soft_page_target: 2.5,
      },
    ],
  }
}

function castPayload() {
  return {
    characters: [
      {
        subject_ref: "maya",
        display_name: "玛雅",
        role: "档案记者",
        voice: "短句、克制",
      },
      {
        subject_ref: "guard",
        display_name: "周警卫",
        role: "保安",
        voice: "程序化措辞",
      },
    ],
  }
}
