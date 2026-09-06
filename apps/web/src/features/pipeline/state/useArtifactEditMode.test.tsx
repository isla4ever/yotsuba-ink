// @vitest-environment happy-dom

import { act, useEffect } from "react"
import { createRoot } from "react-dom/client"
import { describe, expect, it } from "vitest"
import { useArtifactEditMode } from "./useArtifactEditMode"
;(globalThis as Record<string, unknown>).IS_REACT_ACT_ENVIRONMENT = true

describe("useArtifactEditMode", () => {
  it("starts in view mode and resets when the artifact identity changes", () => {
    let latest: ReturnType<typeof useArtifactEditMode> | undefined
    const current = () => {
      if (!latest) throw new Error("hook did not render")
      return latest
    }
    const container = document.createElement("div")
    const root = createRoot(container)

    act(() => {
      root.render(
        <Probe
          canEdit
          identity="candidate-a"
          onValue={(value) => {
            latest = value
          }}
        />,
      )
    })
    expect(current().editing).toBe(false)

    act(() => current().edit())
    expect(current().editing).toBe(true)

    act(() => {
      root.render(
        <Probe
          canEdit
          identity="candidate-b"
          onValue={(value) => {
            latest = value
          }}
        />,
      )
    })
    expect(current().editing).toBe(false)
    act(() => root.unmount())
  })

  it("cannot enter edit mode for a committed artifact", () => {
    let latest: ReturnType<typeof useArtifactEditMode> | undefined
    const current = () => {
      if (!latest) throw new Error("hook did not render")
      return latest
    }
    const container = document.createElement("div")
    const root = createRoot(container)

    act(() => {
      root.render(
        <Probe
          canEdit={false}
          identity="committed-a"
          onValue={(value) => {
            latest = value
          }}
        />,
      )
    })
    act(() => current().edit())
    expect(current().editing).toBe(false)
    act(() => root.unmount())
  })
})

function Probe({
  canEdit,
  identity,
  onValue,
}: {
  canEdit: boolean
  identity: string
  onValue: (value: ReturnType<typeof useArtifactEditMode>) => void
}) {
  const value = useArtifactEditMode(canEdit, identity)
  useEffect(() => onValue(value), [onValue, value])
  return null
}
