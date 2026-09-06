// @vitest-environment happy-dom

import { act, useState } from "react"
import { createRoot } from "react-dom/client"
import { describe, expect, it, vi } from "vitest"
import type { RollingDetailDraft } from "../lib/phase32RollingDetail"
import { RollingDetailArtifactEditor } from "./RollingDetailArtifactEditor"
;(globalThis as Record<string, unknown>).IS_REACT_ACT_ENVIRONMENT = true

describe("RollingDetailArtifactEditor", () => {
  it("selects and reorders frozen Chapters with contiguous ordinals", () => {
    const container = document.createElement("div")
    const root = createRoot(container)
    const onChange = vi.fn()
    act(() =>
      root.render(
        <RollingDetailArtifactEditor
          artifact={detailArtifact()}
          artifactRef="p32-rolling-detail-candidate-1"
          editable
          onChange={onChange}
          referenceContext={referenceContext()}
          revisionLabel="Revision 6"
        />,
      ),
    )

    const chapterTwo = Array.from(
      container.querySelectorAll<HTMLButtonElement>(
        ".phase32-detail-chapter-list > button",
      ),
    )[1]
    act(() => chapterTwo.click())
    expect(container.textContent).toContain("公开听证")
    expect(container.textContent).toContain("卷 02 · 公共核验")

    act(() =>
      container
        .querySelector<HTMLButtonElement>('button[aria-label="上移章节 2"]')
        ?.click(),
    )
    const reordered = onChange.mock.calls.at(-1)?.[0] as RollingDetailDraft
    expect(
      reordered.windows[0].chapters.map((chapter) => chapter.chapter_ref),
    ).toEqual(["chapter-2", "chapter-1"])
    expect(
      reordered.windows[0].chapters.map((chapter) => chapter.ordinal),
    ).toEqual([1, 2])
    expect(reordered.windows[0].chapters[0].volume_ref).toBe("volume-2")

    act(() => root.unmount())
  })

  it("edits chapter and scene literary fields without exposing frozen refs", () => {
    const container = document.createElement("div")
    const root = createRoot(container)
    const onChange = vi.fn()
    act(() =>
      root.render(
        <RollingDetailArtifactEditor
          artifact={detailArtifact()}
          artifactRef="p32-rolling-detail-candidate-1"
          editable
          onChange={onChange}
          referenceContext={referenceContext()}
          revisionLabel="Revision 6"
        />,
      ),
    )

    const job = findField(container, "本章戏剧任务")
    expect(job.dataset.collaborationFieldPath).toBe("chapters.0.dramatic_job")
    expect(job.dataset.collaborationUnit).toBe("chapter-1")
    act(() => setInputValue(job, "迫使机构承认封存日期与签名链冲突。"))
    const edited = onChange.mock.calls.at(-1)?.[0] as RollingDetailDraft
    expect(edited.windows[0].chapters[0].dramatic_job).toContain("签名链")
    expect(edited.windows[0].chapters[0].pov_subject_ref).toBe("maya")
    expect(edited.windows[0].chapters[0].scenes[0].scene_ref).toBe("scene-1")

    act(() => findButton(container, "场景施工").click())
    const location = Array.from(container.querySelectorAll("label"))
      .find((field) => field.textContent?.includes("地点"))
      ?.querySelector("input")
    expect(location?.dataset.collaborationFieldPath).toBe(
      "chapters.0.scenes.0.location",
    )
    expect(location?.dataset.collaborationUnit).toBe("chapter-1")
    act(() => setInputValue(location!, "市档案馆修复室"))
    expect(
      (onChange.mock.calls.at(-1)?.[0] as RollingDetailDraft).windows[0]
        .chapters[0].scenes[0].location,
    ).toBe("市档案馆修复室")
    expect(container.textContent).toContain(
      "新增人物、章节、场景或改变 Volume/POV 范围需走 amendment",
    )

    act(() => root.unmount())
  })

  it("keeps a committed Detail aggregate readonly", () => {
    const container = document.createElement("div")
    const root = createRoot(container)
    act(() =>
      root.render(
        <RollingDetailArtifactEditor
          artifact={detailArtifact()}
          artifactRef="p32-rolling-detail-committed-1"
          editable={false}
          onChange={vi.fn()}
          referenceContext={referenceContext()}
          revisionLabel="Committed Artifact"
        />,
      ),
    )

    expect(
      container.querySelector<HTMLButtonElement>(
        'button[aria-label="下移章节 1"]',
      ),
    ).toBeNull()
    expect(container.querySelectorAll("textarea:not([readonly])")).toHaveLength(
      0,
    )
    expect(container.querySelectorAll("input:not([readonly])")).toHaveLength(0)

    act(() => root.unmount())
  })

  it("edits only Volume-bound Chapter and Scene Cast scopes in repair mode", () => {
    const container = document.createElement("div")
    const root = createRoot(container)
    let latest = detailArtifact()

    function Harness() {
      const [artifact, setArtifact] = useState(detailArtifact())
      return (
        <RollingDetailArtifactEditor
          allowCastScopeEditing
          artifact={artifact}
          artifactRef="p32-provider-operation-rejected"
          editable
          onChange={(next) => {
            latest = (next as RollingDetailDraft)
            setArtifact(latest)
          }}
          referenceContext={referenceContext()}
          revisionLabel="隔离回执"
        />
      )
    }

    act(() => root.render(<Harness />))
    const chapterScope = Array.from(
      container.querySelectorAll("fieldset"),
    ).find((field) => field.textContent?.includes("章节出场范围"))
    const mentor = Array.from(
      chapterScope?.querySelectorAll<HTMLLabelElement>("label") ?? [],
    ).find((label) => label.textContent?.includes("沈砚"))
    act(() => mentor?.querySelector("input")?.click())
    expect(latest.windows[0].chapters[0].cast_subject_refs).toEqual([
      "maya",
      "mentor",
    ])
    expect(latest.windows[0].chapters[0].pov_subject_ref).toBe("maya")

    act(() => findButton(container, "场景施工").click())
    const sceneScope = Array.from(container.querySelectorAll("fieldset")).find(
      (field) => field.textContent?.includes("场景人物范围"),
    )
    const sceneMentor = Array.from(
      sceneScope?.querySelectorAll<HTMLLabelElement>("label") ?? [],
    ).find((label) => label.textContent?.includes("沈砚"))
    act(() => sceneMentor?.querySelector("input")?.click())
    expect(latest.windows[0].chapters[0].scenes[0].cast_subject_refs).toEqual([
      "maya",
      "mentor",
    ])
    expect(container.textContent).toContain(
      "人物只能取自当前 Volume；Scene 人物必须属于 Chapter",
    )

    act(() => root.unmount())
  })
})

function findField(container: HTMLElement, label: string) {
  const field = Array.from(container.querySelectorAll("label")).find((node) =>
    node.textContent?.includes(label),
  )
  const textarea = field?.querySelector("textarea")
  if (!textarea) throw new Error(`Missing field: ${label}`)
  return textarea
}

function findButton(container: HTMLElement, label: string) {
  const button = Array.from(container.querySelectorAll("button")).find((node) =>
    node.textContent?.includes(label),
  )
  if (!button) throw new Error(`Missing button: ${label}`)
  return button
}

function setInputValue(
  element: HTMLInputElement | HTMLTextAreaElement,
  value: string,
) {
  const setter = Object.getOwnPropertyDescriptor(
    Object.getPrototypeOf(element),
    "value",
  )?.set
  setter?.call(element, value)
  element.dispatchEvent(new Event("input", { bubbles: true }))
}

function referenceContext() {
  return {
    volumes: {
      "volume-1": { ref: "volume-1", label: "卷 01 · 原始档案" },
      "volume-2": { ref: "volume-2", label: "卷 02 · 公共核验" },
    },
    cast: {
      maya: { ref: "maya", label: "玛雅" },
      mentor: { ref: "mentor", label: "沈砚" },
    },
    volumeCast: {
      "volume-1": ["maya", "mentor"],
      "volume-2": ["maya"],
    },
  }
}

function detailArtifact(): RollingDetailDraft {
  return {
    windows: [
      {
        window_ref: "window-1",
        ordinal: 1,
        volume_refs: ["volume-1", "volume-2"],
        entry_state: "主角拿到来源不明的复印件。",
        handoff: "下一窗口进入证人保护。",
        next_window_entry_state: "证据进入公共记录。",
        chapters: [
          chapter("chapter-1", 1, "volume-1", "第一份证据", "scene-1"),
          chapter("chapter-2", 2, "volume-2", "公开听证", "scene-2"),
        ],
      },
    ],
  }
}

function chapter(
  chapterRef: string,
  ordinal: number,
  volumeRef: string,
  title: string,
  sceneRef: string,
) {
  return {
    chapter_ref: chapterRef,
    ordinal,
    volume_ref: volumeRef,
    title,
    pov_subject_ref: "maya",
    cast_subject_refs: ["maya"],
    dramatic_job: "把纸面异常推进为公开回应。",
    entry_state: "主角掌握异常水印日期。",
    conflict: "证据可信度与职业安全冲突。",
    stakes: "公开过程会让主角失去原职。",
    exit_state: "证据进入公共记录。",
    hook: "原始封存单被撤回。",
    handoff: "下一章追查审批人。",
    length_hint: 3_500,
    scenes: [
      {
        scene_ref: sceneRef,
        ordinal: 1,
        location: "市档案馆",
        time_context: "闭馆前",
        cast_subject_refs: ["maya"],
        goal: "锁定审批签名。",
        opposition: "记录员拒绝登记。",
        outcome: "异常日期进入正式议程。",
      },
    ],
  }
}
