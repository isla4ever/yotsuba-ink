// @vitest-environment happy-dom

import { act, useEffect } from "react"
import { createRoot } from "react-dom/client"
import { beforeEach, describe, expect, it, vi } from "vitest"
import type { StoryBiblePage, StoryBibleSection } from "../contracts/storyBible"
import { useStoryBible } from "./useStoryBible"

const mocks = vi.hoisted(() => ({
  getStoryBiblePage: vi.fn(),
}))

vi.mock("../services/storyBibleApi", () => ({
  getStoryBiblePage: mocks.getStoryBiblePage,
}))
;(globalThis as Record<string, unknown>).IS_REACT_ACT_ENVIRONMENT = true

describe("useStoryBible", () => {
  beforeEach(() => vi.clearAllMocks())

  it("keeps committed entries visible while the authority revision refreshes", async () => {
    const initial = deferred<StoryBiblePage>()
    const refreshed = deferred<StoryBiblePage>()
    mocks.getStoryBiblePage
      .mockReturnValueOnce(initial.promise)
      .mockReturnValueOnce(refreshed.promise)
    const states: Array<ReturnType<typeof useStoryBible>> = []
    const container = document.createElement("div")
    const root = createRoot(container)

    await act(async () => {
      root.render(
        <Probe
          authorityRevision="revision-1"
          onValue={(value) => states.push(value)}
        />,
      )
    })
    expect(states.at(-1)?.status).toBe("loading")

    await act(async () => initial.resolve(storyBiblePage("旧的已提交结构")))
    await vi.waitFor(() => expect(states.at(-1)?.status).toBe("ready"))
    expect(states.at(-1)?.items[0].title).toBe("旧的已提交结构")

    await act(async () => {
      root.render(
        <Probe
          authorityRevision="revision-2"
          onValue={(value) => states.push(value)}
        />,
      )
    })
    await vi.waitFor(() => expect(states.at(-1)?.status).toBe("refreshing"))
    expect(states.at(-1)?.items[0].title).toBe("旧的已提交结构")

    await act(async () => refreshed.resolve(storyBiblePage("新的已提交结构")))
    await vi.waitFor(() => expect(states.at(-1)?.status).toBe("ready"))
    expect(states.at(-1)?.items[0].title).toBe("新的已提交结构")
    expect(mocks.getStoryBiblePage).toHaveBeenCalledTimes(2)

    act(() => root.unmount())
  })
})

function Probe({
  authorityRevision,
  onValue,
}: {
  authorityRevision: string
  onValue: (value: ReturnType<typeof useStoryBible>) => void
}) {
  const value = useStoryBible("run-story-bible", "structure", authorityRevision)
  useEffect(() => {
    onValue(value)
  }, [onValue, value])
  return null
}

function storyBiblePage(title: string): StoryBiblePage {
  return {
    architecture_version: "phase32-routes-v1",
    run_id: "run-story-bible",
    project_id: "project-story-bible",
    creation_route_id: "short_novel",
    route_revision: "r1",
    definition_digest: "a".repeat(64),
    section: "structure",
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
      ],
      source_artifact_count: 1,
      character_count: 0,
      relationship_count: 0,
      structure_count: 1,
      accepted_unit_count: 0,
      continuity_count: 0,
      tracked_promise_count: 0,
      open_question_count: 0,
      formal_fact_count: 0,
      formal_writeback_status: "not_started",
    },
    items: [
      {
        entry_ref: "anchor-opening",
        kind: "story_anchor",
        title,
        body: "主角决定公开调查签名链。",
        detail: "该结构直接来自已提交 Story Map。",
        status: "committed",
        ordinal: 1,
        parent_ref: "",
        unit_ref: "",
        subject_refs: [],
        promise_refs: [],
        tags: [],
        authority: "committed_artifact",
        confidence: "direct",
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

function deferred<T>() {
  let resolve: (value: T) => void = () => undefined
  const promise = new Promise<T>((next) => {
    resolve = next
  })
  return { promise, resolve }
}
