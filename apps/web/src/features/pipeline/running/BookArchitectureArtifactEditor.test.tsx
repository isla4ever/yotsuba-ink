// @vitest-environment happy-dom

import { act } from "react"
import { createRoot } from "react-dom/client"
import { describe, expect, it, vi } from "vitest"
import type { BookArchitectureDraft } from "../lib/phase32BookArchitecture"
import { BookArchitectureArtifactEditor } from "./BookArchitectureArtifactEditor"
;(globalThis as Record<string, unknown>).IS_REACT_ACT_ENVIRONMENT = true

describe("BookArchitectureArtifactEditor", () => {
  it("selects and reorders Parts while preserving refs and contiguous ordinals", () => {
    const container = document.createElement("div")
    const root = createRoot(container)
    const onChange = vi.fn()
    act(() =>
      root.render(
        <BookArchitectureArtifactEditor
          artifact={bookArchitecture()}
          artifactRef="p32-book-architecture-candidate-1"
          editable
          revisionLabel="Revision 2"
          onChange={onChange}
        />,
      ),
    )

    const partTwo = Array.from(
      container.querySelectorAll<HTMLButtonElement>(
        ".book-architecture-part-list > button",
      ),
    )[1]
    act(() => partTwo.click())
    expect(container.textContent).toContain("公开全部证据付出什么")

    act(() =>
      container
        .querySelector<HTMLButtonElement>('button[aria-label="上移 Part 2"]')
        ?.click(),
    )
    const reordered = onChange.mock.calls.at(-1)?.[0] as BookArchitectureDraft
    expect(reordered.parts.map((part) => part.part_ref)).toEqual([
      "part-2",
      "part-1",
    ])
    expect(reordered.parts.map((part) => part.ordinal)).toEqual([1, 2])

    act(() => root.unmount())
  })

  it("edits Part content and adds an unresolved obligation without exposing refs", () => {
    const container = document.createElement("div")
    const root = createRoot(container)
    const onChange = vi.fn()
    act(() =>
      root.render(
        <BookArchitectureArtifactEditor
          artifact={bookArchitecture()}
          artifactRef="p32-book-architecture-candidate-1"
          editable
          revisionLabel="Revision 2"
          onChange={onChange}
        />,
      ),
    )

    const entryState = findField(container, "进入状态")
    act(() => setInputValue(entryState, "主角拿到一份无法公开的原始档案。"))
    const edited = onChange.mock.calls.at(-1)?.[0] as BookArchitectureDraft
    expect(edited.parts[0].part_ref).toBe("part-1")
    expect(edited.parts[0].entry_state).toContain("无法公开")
    expect(container.textContent).toContain("稳定引用保持只读")

    const composer = container.querySelector<HTMLInputElement>(
      'input[placeholder="补充一个需要后续 Part 继续处理的责任"]',
    )!
    act(() => setInputValue(composer, "确认备份档案的保管者。"))
    const add = composer
      .closest(".book-architecture-composer")
      ?.querySelector<HTMLButtonElement>("button")
    if (!add) throw new Error("Missing unresolved-obligation add button")
    act(() => add.click())
    expect(
      (onChange.mock.calls.at(-1)?.[0] as BookArchitectureDraft).parts[0]
        .unresolved_obligations,
    ).toContain("确认备份档案的保管者。")

    act(() => root.unmount())
  })

  it("makes a committed aggregate readonly and removes all composers", () => {
    const container = document.createElement("div")
    const root = createRoot(container)
    act(() =>
      root.render(
        <BookArchitectureArtifactEditor
          artifact={bookArchitecture()}
          artifactRef="p32-book-architecture-committed-1"
          editable={false}
          revisionLabel="Committed Artifact"
          onChange={vi.fn()}
        />,
      ),
    )

    expect(
      container.querySelector<HTMLButtonElement>(
        'button[aria-label="下移 Part 1"]',
      ),
    ).toBeNull()
    expect(container.querySelectorAll("textarea:not([readonly])")).toHaveLength(
      0,
    )
    expect(container.querySelector(".book-architecture-composer")).toBeNull()

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

function bookArchitecture(): BookArchitectureDraft {
  return {
    book_promise: "一场关于城市记忆与公开代价的长期调查。",
    ending_conditions: ["证据链公开。", "主角承担公开真相的长期后果。"],
    parts: [
      {
        part_ref: "part-1",
        ordinal: 1,
        entry_state: "主角只相信公开档案。",
        dramatic_question: "她能否证明档案正在被系统性删改？",
        promise_refs: ["promise-truth"],
        turning_point_refs: ["turn-erasure"],
        exit_state: "第一份原始证据进入公众视野。",
        unresolved_obligations: ["找到签发删改命令的人。"],
      },
      {
        part_ref: "part-2",
        ordinal: 2,
        entry_state: "调查从机构内部转向公共听证。",
        dramatic_question: "她愿意为公开全部证据付出什么？",
        promise_refs: ["promise-truth", "promise-cost"],
        turning_point_refs: ["turn-hearing", "turn-choice"],
        exit_state: "事实被承认，但主角失去原职。",
        unresolved_obligations: [],
      },
    ],
  }
}
