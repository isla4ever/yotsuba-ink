// @vitest-environment happy-dom

import { act } from "react"
import { createRoot } from "react-dom/client"
import { describe, expect, it, vi } from "vitest"
import type { BeatBoardDraft } from "../lib/phase32BeatBoard"
import { BeatBoardArtifactEditor } from "./BeatBoardArtifactEditor"
;(globalThis as Record<string, unknown>).IS_REACT_ACT_ENVIRONMENT = true

describe("BeatBoardArtifactEditor", () => {
  it("navigates beats and keeps reading mode free of form fields", () => {
    const container = document.createElement("div")
    const root = createRoot(container)
    act(() =>
      root.render(
        <BeatBoardArtifactEditor
          artifact={beatBoardPayload()}
          artifactRef="p32-beat-board-committed-1"
          editable={false}
          onChange={vi.fn()}
          referenceContext={referenceContext()}
          revisionLabel="已确认版本"
        />,
      ),
    )

    expect(container.querySelectorAll("input, textarea, select")).toHaveLength(
      0,
    )
    const secondBeat = container.querySelectorAll<HTMLButtonElement>(
      ".beat-board-rail-list > button",
    )[1]
    act(() => secondBeat.click())
    expect(container.textContent).toContain("拒绝交出原件")

    act(() => findButton(container, "任务与铺垫").click())
    expect(container.textContent).toContain("payoff-public-record")

    act(() => root.unmount())
  })

  it("edits only the selected beat and preserves frozen identity while reordering", () => {
    const container = document.createElement("div")
    const root = createRoot(container)
    const onChange = vi.fn()
    act(() =>
      root.render(
        <BeatBoardArtifactEditor
          artifact={beatBoardPayload()}
          artifactRef="p32-beat-board-candidate-1"
          editable
          onChange={onChange}
          referenceContext={referenceContext()}
          revisionLabel="Revision 4"
        />,
      ),
    )

    const decision = container.querySelector<HTMLTextAreaElement>(
      'textarea[aria-label="台面决定"]',
    )!
    act(() => setInputValue(decision, "主角把签名页交给现场记录员。"))
    let changed = onChange.mock.calls.at(-1)?.[0] as BeatBoardDraft
    expect(changed.beats[0].character_decision).toContain("记录员")
    expect(changed.beats[0].beat_ref).toBe("beat-1")
    expect(changed.beats[1]).toEqual(beatBoardPayload().beats[1])

    act(() =>
      container
        .querySelector<HTMLButtonElement>('button[aria-label="下移节拍 1"]')
        ?.click(),
    )
    changed = (onChange.mock.calls.at(-1)?.[0] as BeatBoardDraft)
    expect(changed.beats.map((beat) => beat.beat_ref)).toEqual([
      "beat-2",
      "beat-1",
    ])

    act(() => root.unmount())
  })
})

function findButton(container: HTMLElement, label: string) {
  const button = Array.from(container.querySelectorAll("button")).find((item) =>
    item.textContent?.includes(label),
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
  element.dispatchEvent(new Event("change", { bubbles: true }))
}

function referenceContext() {
  return {
    brief: {
      audiencePromise: "证据驱动的调查样片",
      endingEffect: "签名页进入公共记录",
      sampleType: "调查悬疑样片",
      targetMinutes: 12,
      tone: "冷峻克制",
      visibleConflict: "闭馆前证明签名页被替换",
    },
    cast: {
      maya: { label: "玛雅", ref: "maya", role: "档案记者" },
    },
  }
}

function beatBoardPayload(): BeatBoardDraft {
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
