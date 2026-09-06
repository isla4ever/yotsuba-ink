import { useCallback, useEffect, useRef, useState, type RefObject } from "react"
import type {
  CollaborationStageId,
  SelectionAnchor,
} from "../contracts/authorCollaboration"

type Options = {
  enabled: boolean
  rootRef: RefObject<HTMLElement | null>
  sourceRef: string
  stageId: CollaborationStageId
}

type SelectionTarget = HTMLInputElement | HTMLTextAreaElement

export function useStageSelectionCapture({
  enabled,
  rootRef,
  sourceRef,
  stageId,
}: Options) {
  const [selection, setSelection] = useState<SelectionAnchor | null>(null)
  const captureRevision = useRef(0)

  const clearSelection = useCallback(() => {
    captureRevision.current += 1
    setSelection(null)
  }, [])

  useEffect(() => {
    clearSelection()
  }, [clearSelection, sourceRef, stageId])

  useEffect(() => {
    if (!enabled) return undefined

    const capture = (event: Event) => {
      const target = event.target
      if (!isSelectionTarget(target) || !rootRef.current?.contains(target))
        return
      const fieldPath = target.dataset.collaborationFieldPath ?? ""
      if (!fieldPath) return
      if (!sourceRef) {
        clearSelection()
        return
      }
      const selectionStart = target.selectionStart ?? 0
      const selectionEnd = target.selectionEnd ?? 0
      if (selectionEnd <= selectionStart) {
        clearSelection()
        return
      }
      const revision = ++captureRevision.current
      void createSelectionAnchor({
        fieldPath,
        fieldValue: target.value,
        selectionEnd,
        selectionStart,
        sourceRef,
        stageId,
        unitRef: target.dataset.collaborationUnit || "artifact",
      })
        .then((anchor) => {
          if (captureRevision.current === revision) setSelection(anchor)
        })
        .catch(() => {
          if (captureRevision.current === revision) setSelection(null)
        })
    }
    const invalidate = (event: Event) => {
      const target = event.target
      if (!isSelectionTarget(target) || !rootRef.current?.contains(target))
        return
      if (selection?.field_path === target.dataset.collaborationFieldPath)
        clearSelection()
    }

    document.addEventListener("select", capture, true)
    document.addEventListener("pointerup", capture, true)
    document.addEventListener("keyup", capture, true)
    document.addEventListener("input", invalidate, true)
    return () => {
      document.removeEventListener("select", capture, true)
      document.removeEventListener("pointerup", capture, true)
      document.removeEventListener("keyup", capture, true)
      document.removeEventListener("input", invalidate, true)
    }
  }, [
    clearSelection,
    enabled,
    rootRef,
    selection?.field_path,
    sourceRef,
    stageId,
  ])

  return { clearSelection, selection }
}

export async function createSelectionAnchor({
  fieldPath,
  fieldValue,
  selectionEnd,
  selectionStart,
  sourceRef,
  stageId,
  unitRef,
}: {
  fieldPath: string
  fieldValue: string
  selectionEnd: number
  selectionStart: number
  sourceRef: string
  stageId: CollaborationStageId
  unitRef: string
}): Promise<SelectionAnchor> {
  const selectedText = fieldValue.slice(selectionStart, selectionEnd)
  if (!selectedText) throw new Error("Selection is empty")
  const codePointStart = Array.from(fieldValue.slice(0, selectionStart)).length
  const selectedCharCount = Array.from(selectedText).length
  return {
    anchor_id:
      globalThis.crypto?.randomUUID?.() ??
      `selection-${Date.now()}-${codePointStart}`,
    stage_id: stageId,
    source_ref: sourceRef,
    unit_ref: unitRef,
    field_path: fieldPath,
    field_hash: await sha256(fieldValue),
    selection_start: codePointStart,
    selection_end: codePointStart + selectedCharCount,
    selected_text_hash: await sha256(selectedText),
    selected_char_count: selectedCharCount,
    preview: selectionPreview(selectedText),
    selected_text: selectedText,
    created_at: new Date().toISOString(),
  }
}

async function sha256(value: string) {
  const bytes = new TextEncoder().encode(value)
  const digest = await globalThis.crypto.subtle.digest("SHA-256", bytes)
  return Array.from(new Uint8Array(digest), (byte) =>
    byte.toString(16).padStart(2, "0"),
  ).join("")
}

function selectionPreview(value: string) {
  const compact = value.replace(/\s+/gu, " ").trim()
  return Array.from(compact).length > 80
    ? `${Array.from(compact).slice(0, 80).join("")}...`
    : compact
}

function isSelectionTarget(
  target: EventTarget | null,
): target is SelectionTarget {
  return (
    target instanceof HTMLInputElement || target instanceof HTMLTextAreaElement
  )
}
