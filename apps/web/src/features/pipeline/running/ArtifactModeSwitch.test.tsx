// @vitest-environment happy-dom

import { act } from "react"
import { createRoot } from "react-dom/client"
import { describe, expect, it, vi } from "vitest"
import { ArtifactModeSwitch } from "./ArtifactModeSwitch"
;(globalThis as Record<string, unknown>).IS_REACT_ACT_ENVIRONMENT = true

describe("ArtifactModeSwitch", () => {
  it("keeps icon-only mobile controls named and preserves the edit lock", () => {
    const container = document.createElement("div")
    const root = createRoot(container)
    act(() =>
      root.render(
        <ArtifactModeSwitch
          canEdit={false}
          editing={false}
          onEdit={vi.fn()}
          onShow={vi.fn()}
        />,
      ),
    )

    const reading = container.querySelector<HTMLButtonElement>(
      'button[aria-label="阅读模式"]',
    )
    const editing = container.querySelector<HTMLButtonElement>(
      'button[aria-label="编辑模式"]',
    )
    expect(reading?.getAttribute("aria-pressed")).toBe("true")
    expect(reading?.title).toBe("阅读模式")
    expect(editing?.disabled).toBe(true)
    expect(editing?.title).toBe("编辑模式")

    act(() => root.unmount())
  })

  it("names formal committed-Artifact editing without changing the control", () => {
    const container = document.createElement("div")
    const root = createRoot(container)
    act(() =>
      root.render(
        <ArtifactModeSwitch
          canEdit
          editLabel="修订"
          editTitle="正式修订已提交版本"
          editing={false}
          onEdit={vi.fn()}
          onShow={vi.fn()}
        />,
      ),
    )

    const editing = container.querySelector<HTMLButtonElement>(
      'button[aria-label="正式修订已提交版本"]',
    )
    expect(editing?.textContent).toContain("修订")
    expect(editing?.disabled).toBe(false)

    act(() => root.unmount())
  })
})
