import type {
  RollingDetailChapterDraft,
  RollingDetailReferenceContext,
  RollingDetailSceneDraft,
} from "../lib/phase32RollingDetail"

export function RollingDetailChapterCastScopeEditor({
  chapter,
  onChange,
  referenceContext,
}: {
  chapter: RollingDetailChapterDraft
  onChange: (patch: Partial<RollingDetailChapterDraft>) => void
  referenceContext: RollingDetailReferenceContext
}) {
  const allowedRefs =
    referenceContext.volumeCast[chapter.volume_ref] ?? chapter.cast_subject_refs
  const allowedSet = new Set(allowedRefs)
  const visibleRefs = [
    ...allowedRefs,
    ...chapter.cast_subject_refs.filter((ref) => !allowedSet.has(ref)),
  ]

  const toggle = (subjectRef: string) => {
    const selected = new Set(chapter.cast_subject_refs)
    if (selected.has(subjectRef)) selected.delete(subjectRef)
    else selected.add(subjectRef)
    const castSubjectRefs = visibleRefs.filter((ref) => selected.has(ref))
    onChange({
      cast_subject_refs: castSubjectRefs,
      scenes: chapter.scenes.map((scene) => ({
        ...scene,
        cast_subject_refs: scene.cast_subject_refs.filter((ref) =>
          selected.has(ref),
        ),
      })),
    })
  }

  return (
    <fieldset className="phase32-detail-cast-repair">
      <legend>合同修复 · 章节出场范围</legend>
      <p>只能从当前卷已冻结人物中调整；POV 必须保留。</p>
      <div>
        {visibleRefs.map((subjectRef) => {
          const checked = chapter.cast_subject_refs.includes(subjectRef)
          const requiredByScene = chapter.scenes.some(
            (scene) =>
              scene.cast_subject_refs.length === 1 &&
              scene.cast_subject_refs[0] === subjectRef,
          )
          const locked =
            subjectRef === chapter.pov_subject_ref || requiredByScene
          const outsideVolume = !allowedSet.has(subjectRef)
          return (
            <label key={subjectRef}>
              <input
                checked={checked}
                disabled={locked}
                onChange={() => toggle(subjectRef)}
                type="checkbox"
              />
              <span>
                {referenceContext.cast[subjectRef]?.label ?? subjectRef}
              </span>
              {subjectRef === chapter.pov_subject_ref ? (
                <small>POV</small>
              ) : null}
              {requiredByScene && subjectRef !== chapter.pov_subject_ref ? (
                <small>场景唯一</small>
              ) : null}
              {outsideVolume ? <small className="is-risk">越界</small> : null}
            </label>
          )
        })}
      </div>
    </fieldset>
  )
}

export function RollingDetailSceneCastScopeEditor({
  chapter,
  onChange,
  referenceContext,
  scene,
}: {
  chapter: RollingDetailChapterDraft
  onChange: (patch: Partial<RollingDetailSceneDraft>) => void
  referenceContext: RollingDetailReferenceContext
  scene: RollingDetailSceneDraft
}) {
  const toggle = (subjectRef: string) => {
    const selected = new Set(scene.cast_subject_refs)
    if (selected.has(subjectRef)) selected.delete(subjectRef)
    else selected.add(subjectRef)
    onChange({
      cast_subject_refs: chapter.cast_subject_refs.filter((ref) =>
        selected.has(ref),
      ),
    })
  }

  return (
    <fieldset className="phase32-detail-scene-cast-repair">
      <legend>场景人物范围</legend>
      <div>
        {chapter.cast_subject_refs.map((subjectRef) => {
          const checked = scene.cast_subject_refs.includes(subjectRef)
          return (
            <label key={subjectRef}>
              <input
                checked={checked}
                disabled={checked && scene.cast_subject_refs.length === 1}
                onChange={() => toggle(subjectRef)}
                type="checkbox"
              />
              <span>
                {referenceContext.cast[subjectRef]?.label ?? subjectRef}
              </span>
            </label>
          )
        })}
      </div>
    </fieldset>
  )
}
