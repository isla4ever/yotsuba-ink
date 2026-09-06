// @vitest-environment happy-dom

import { afterEach, describe, expect, it, vi } from "vitest"
import { getStoryBiblePage, parseStoryBiblePage } from "./storyBibleApi"

describe("Phase 32 Story Bible API", () => {
  afterEach(() => vi.unstubAllGlobals())

  it("parses route-aware committed Artifact and formal Canon entries", () => {
    const page = storyBiblePage()
    expect(parseStoryBiblePage(page, "run-1", "structure")).toEqual(page)

    const formalPage = {
      ...page,
      section: "continuity" as const,
      summary: {
        ...page.summary,
        formal_fact_count: 1,
        formal_writeback_status: "committed" as const,
      },
      items: [formalFactEntry()],
    }
    expect(parseStoryBiblePage(formalPage, "run-1", "continuity")).toEqual(
      formalPage,
    )
  })

  it("rejects legacy identity and non-direct entries", () => {
    expect(() =>
      parseStoryBiblePage(
        { ...storyBiblePage(), architecture_version: "phase27-vnext" },
        "run-1",
        "structure",
      ),
    ).toThrow("故事圣经接口返回了无法识别的数据")

    const page = storyBiblePage()
    page.items[0].confidence = ("model_guess" as "direct")
    expect(() => parseStoryBiblePage(page, "run-1", "structure")).toThrow(
      "故事圣经接口返回了无法识别的数据",
    )

    const invalidStatus = storyBiblePage()
    invalidStatus.summary.formal_writeback_status =
      ("pending_contract" as "not_started")
    expect(() =>
      parseStoryBiblePage(invalidStatus, "run-1", "structure"),
    ).toThrow("故事圣经接口返回了无法识别的数据")
  })

  it("uses the canonical paged route", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify(storyBiblePage()), {
        headers: { "Content-Type": "application/json" },
        status: 200,
      }),
    )
    vi.stubGlobal("fetch", fetchMock)

    await getStoryBiblePage("run-1", "structure")

    expect(fetchMock).toHaveBeenCalledWith(
      "/api/runs/run-1/story-bible?section=structure&limit=50",
      { signal: undefined },
    )
  })
})

function storyBiblePage() {
  return {
    architecture_version: "phase32-routes-v1" as const,
    run_id: "run-1",
    project_id: "project-1",
    creation_route_id: "short_novel" as const,
    route_revision: "r3",
    definition_digest: "a".repeat(64),
    section: "structure" as const,
    summary: {
      title: "失序档案",
      route_label: "短中篇小说",
      run_status: "running",
      active_stage_id: "text",
      updated_at: "2026-08-25T12:00:00+08:00",
      projection_revision: "b".repeat(64),
      available_sections: [
        "overview",
        "cast",
        "structure",
        "units",
        "continuity",
      ] as const,
      source_artifact_count: 4,
      character_count: 2,
      relationship_count: 1,
      structure_count: 4,
      accepted_unit_count: 1,
      continuity_count: 3,
      tracked_promise_count: 1,
      open_question_count: 1,
      formal_fact_count: 0,
      formal_writeback_status:
        "not_started" as "not_started" | "in_progress" | "recovery_required" | "committed",
    },
    items: [
      {
        entry_ref: "anchor-opening",
        kind: "story_anchor" as const,
        title: "公开质疑签名系统",
        body: "证词将在午夜永久封存。",
        detail: "选择/揭示：主角发现水印日期异常。",
        status: "committed" as const,
        ordinal: 1,
        parent_ref: "",
        unit_ref: "",
        subject_refs: [],
        promise_refs: ["promise-truth-cost"],
        tags: [],
        authority: "committed_artifact" as const,
        confidence: "direct" as const,
        source: {
          stage_id: "story_map",
          artifact_kind: "story_map",
          artifact_ref: `p32-story_map-committed-${"c".repeat(64)}`,
          payload_digest: "c".repeat(64),
          source_path: "story_map.anchors[0]",
          committed_at: "2026-08-25T12:00:00+08:00",
        },
      },
    ],
    total: 1,
    limit: 50,
    next_cursor: null,
  }
}

function formalFactEntry() {
  return {
    entry_ref: "fact-watermark-date",
    kind: "formal_fact" as const,
    title: "档案水印日期晚于封存记录",
    body: "水印日期比封存记录晚了三天。",
    detail: "archive-ledger · watermark_date · +3d",
    status: "verified" as const,
    ordinal: 1,
    parent_ref: "",
    unit_ref: "unit-1",
    subject_refs: ["archive-ledger"],
    promise_refs: [],
    tags: ["observed", "active"],
    authority: "canon" as const,
    confidence: "direct" as const,
    source: {
      stage_id: "text",
      artifact_kind: "short_prose_unit",
      artifact_ref: `p32-text-committed-${"d".repeat(64)}`,
      payload_digest: "d".repeat(64),
      source_path: "canon.transaction.fact-watermark-date",
      committed_at: "2026-08-25T12:05:00+08:00",
    },
  }
}
