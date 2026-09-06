import { useCallback, useEffect, useState } from "react"

export function useArtifactEditMode(
  canEdit: boolean,
  artifactIdentity: string,
) {
  const [requestedMode, setRequestedMode] = useState<"view" | "edit">("view")

  useEffect(() => {
    setRequestedMode("view")
  }, [artifactIdentity, canEdit])

  const editing = canEdit && requestedMode === "edit"
  const show = useCallback(() => setRequestedMode("view"), [])
  const edit = useCallback(() => {
    if (canEdit) setRequestedMode("edit")
  }, [canEdit])

  return { edit, editing, show }
}
