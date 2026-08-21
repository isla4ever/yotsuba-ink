// @vitest-environment happy-dom

import { act } from "react"
import { createRoot } from "react-dom/client"
import { describe, expect, it } from "vitest"
import { BookLoader, BookLoaderLayer } from "./BookLoader"
;(globalThis as Record<string, unknown>).IS_REACT_ACT_ENVIRONMENT = true

describe("BookLoaderLayer", () => {
  it("keeps the global overlay as the only loading status while it is visible", () => {
    const container = document.createElement("div")
    const root = createRoot(container)

    act(() =>
      root.render(
        <BookLoaderLayer overlayVisible>
          <BookLoader variant="panel" label="阶段加载" />
          <BookLoader variant="compact" label="局部加载" />
          <BookLoader variant="overlay" label="工作台加载" />
        </BookLoaderLayer>,
      ),
    )

    const loaders = container.querySelectorAll('[role="status"]')
    expect(loaders).toHaveLength(1)
    expect(loaders[0]?.textContent).toContain("工作台加载")
    expect(container.textContent).not.toContain("阶段加载")
    expect(container.textContent).not.toContain("局部加载")

    act(() => root.unmount())
  })

  it("restores local loading feedback after the overlay leaves", () => {
    const container = document.createElement("div")
    const root = createRoot(container)

    act(() =>
      root.render(
        <BookLoaderLayer overlayVisible={false}>
          <BookLoader variant="panel" label="阶段加载" />
        </BookLoaderLayer>,
      ),
    )

    expect(container.querySelectorAll('[role="status"]')).toHaveLength(1)
    expect(container.textContent).toContain("阶段加载")

    act(() => root.unmount())
  })
})
