import { Scan, ZoomIn, ZoomOut } from "lucide-react"
import { useCallback, useEffect, useMemo, useRef, useState } from "react"
import ForceGraph3D, { type ForceGraphMethods } from "react-force-graph-3d"
import * as THREE from "three"
import type { CharacterBibleDraft } from "../lib/phase32Cast"
import {
  connectedSubjectIds,
  projectCharacterGraph,
  relationTouches,
  type CharacterGraphEdge,
  type CharacterGraphNode,
} from "../lib/characterGraph"
import {
  characterCameraBounds,
  characterCameraFrame,
  createCharacterAnchorForce,
  initialCharacterLayout,
  type SpatialCharacterNode,
} from "./characterGraph3DLayout"
import {
  createCharacterNodeObject,
  createRelationLabel,
  createStaticStarfield,
  disposeCharacterObject,
  positionRelationLabel,
  relationCurve,
  relationCurveRotation,
} from "./characterGraph3DObjects"

type Props = {
  artifact: CharacterBibleDraft
  onSelect: (subjectId: string | null) => void
  selectedId: string | null
}

type CameraAction = "fit" | "zoom-in" | "zoom-out"

export default function CharacterGraph3D({
  artifact,
  onSelect,
  selectedId,
}: Props) {
  const graphRef = useRef<ForceGraphMethods | undefined>(undefined)
  const containerRef = useRef<HTMLDivElement | null>(null)
  const pauseTimerRef = useRef<number | null>(null)
  const readyRef = useRef(false)
  const settledRef = useRef(false)
  const tickRef = useRef(0)
  const [hoveredId, setHoveredId] = useState<string | null>(null)
  const [size, setSize] = useState({ height: 430, width: 300 })
  const graph = useMemo(() => projectCharacterGraph(artifact), [artifact])
  const portrait = size.width / Math.max(1, size.height) < 1.14
  const compact = size.width < 560
  const focusId = hoveredId || selectedId || ""
  const neighborhood = useMemo(
    () => connectedSubjectIds(graph, focusId),
    [focusId, graph],
  )
  const graphData = useMemo(
    () => ({
      links: graph.links.map((edge) => ({ ...edge })),
      nodes: initialCharacterLayout(graph.nodes, portrait),
    }),
    [graph, portrait],
  )
  const webglAvailable = useMemo(() => supportsWebGL(), [])

  const resumeFor = useCallback((duration: number) => {
    if (!readyRef.current) return
    graphRef.current?.resumeAnimation?.()
    if (pauseTimerRef.current !== null)
      window.clearTimeout(pauseTimerRef.current)
    pauseTimerRef.current = window.setTimeout(
      () => {
        if (!containerRef.current?.matches(":hover"))
          graphRef.current?.pauseAnimation?.()
      },
      Math.max(90, duration + 90),
    )
  }, [])

  const fitGraph = useCallback(
    (duration: number) => {
      const api = graphRef.current
      if (!api || !readyRef.current) return
      const frame = characterCameraFrame(
        graphData.nodes,
        size.width,
        size.height,
      )
      resumeFor(duration)
      api.cameraPosition(
        {
          x: frame.target.x,
          y: frame.target.y,
          z: frame.target.z + frame.distance,
        },
        frame.target,
        duration,
      )
    },
    [graphData.nodes, resumeFor, size.height, size.width],
  )

  const focusSubject = useCallback(
    (subjectId: string, duration: number) => {
      const api = graphRef.current
      if (!api || !readyRef.current) return
      const node = graphData.nodes.find((item) => item.id === subjectId)
      if (
        !node ||
        !Number.isFinite(node.x) ||
        !Number.isFinite(node.y) ||
        !Number.isFinite(node.z)
      )
        return
      const frame = characterCameraFrame(
        graphData.nodes,
        size.width,
        size.height,
      )
      const ratio = compact ? 0.16 : 0.25
      const target = {
        x: frame.target.x + ((node.x ?? 0) - frame.target.x) * ratio,
        y: frame.target.y + ((node.y ?? 0) - frame.target.y) * ratio,
        z: frame.target.z + ((node.z ?? 0) - frame.target.z) * ratio,
      }
      resumeFor(duration)
      api.cameraPosition(
        {
          x: target.x,
          y: target.y,
          z: target.z + frame.distance * (compact ? 1.04 : 1.08),
        },
        target,
        duration,
      )
    },
    [compact, graphData.nodes, resumeFor, size.height, size.width],
  )

  const requestCamera = useCallback(
    (action: CameraAction) => {
      const reducedMotion = window.matchMedia(
        "(prefers-reduced-motion: reduce)",
      ).matches
      const duration = reducedMotion ? 0 : 300
      if (action === "fit") {
        fitGraph(duration)
        return
      }
      const api = graphRef.current
      if (!api || !readyRef.current) return
      const camera = api.camera()
      const frame = characterCameraFrame(
        graphData.nodes,
        size.width,
        size.height,
      )
      const targetNode = graphData.nodes.find((node) => node.id === selectedId)
      const target =
        targetNode &&
        Number.isFinite(targetNode.x) &&
        Number.isFinite(targetNode.y) &&
        Number.isFinite(targetNode.z)
          ? { x: targetNode.x ?? 0, y: targetNode.y ?? 0, z: targetNode.z ?? 0 }
          : frame.target
      const delta = {
        x: camera.position.x - target.x,
        y: camera.position.y - target.y,
        z: camera.position.z - target.z,
      }
      const currentDistance = Math.max(1, Math.hypot(delta.x, delta.y, delta.z))
      const bounds = characterCameraBounds(frame.distance)
      const nextDistance = Math.min(
        bounds.maximum,
        Math.max(
          bounds.minimum,
          currentDistance * (action === "zoom-in" ? 0.78 : 1.28),
        ),
      )
      const factor = nextDistance / currentDistance
      resumeFor(duration)
      api.cameraPosition(
        {
          x: target.x + delta.x * factor,
          y: target.y + delta.y * factor,
          z: target.z + delta.z * factor,
        },
        target,
        duration,
      )
    },
    [fitGraph, graphData.nodes, resumeFor, selectedId, size.height, size.width],
  )

  useEffect(() => {
    const element = containerRef.current
    if (!element) return
    const observer = new ResizeObserver(([entry]) =>
      setSize({
        height: Math.max(320, Math.floor(entry.contentRect.height)),
        width: Math.max(300, Math.floor(entry.contentRect.width)),
      }),
    )
    observer.observe(element)
    return () => observer.disconnect()
  }, [])

  useEffect(() => {
    if (!selectedId || !settledRef.current) return
    const reducedMotion = window.matchMedia(
      "(prefers-reduced-motion: reduce)",
    ).matches
    focusSubject(selectedId, reducedMotion ? 0 : 380)
  }, [focusSubject, selectedId])

  useEffect(() => {
    if (!settledRef.current) return
    const frame = window.requestAnimationFrame(() => {
      const reducedMotion = window.matchMedia(
        "(prefers-reduced-motion: reduce)",
      ).matches
      if (selectedId) focusSubject(selectedId, reducedMotion ? 0 : 320)
      else fitGraph(reducedMotion ? 0 : 360)
    })
    return () => window.cancelAnimationFrame(frame)
  }, [fitGraph, focusSubject, selectedId, size.height, size.width])

  useEffect(() => {
    const api = graphRef.current
    if (!api) return
    api.d3Force("charge")?.strength?.(compact ? -500 : -690)
    api.d3Force("link")?.distance?.(compact ? 126 : 164)
    api.d3Force("center")?.strength?.(0.018)
    api.d3Force(
      "characterAnchor",
      createCharacterAnchorForce(graphData.nodes as SpatialCharacterNode[]),
    )
    const frame = characterCameraFrame(graphData.nodes, size.width, size.height)
    const bounds = characterCameraBounds(frame.distance)
    const controls = api.controls?.() as {
      maxDistance?: number
      minDistance?: number
    } | undefined
    if (controls) {
      controls.maxDistance = bounds.maximum
      controls.minDistance = bounds.minimum
    }
  }, [compact, graphData.nodes, size.height, size.width])

  useEffect(() => {
    const api = graphRef.current
    const scene = api?.scene?.()
    if (!scene) return
    const starfield = createStaticStarfield(compact ? 180 : 360)
    scene.add(starfield)
    return () => {
      scene.remove(starfield)
      disposeCharacterObject(starfield)
    }
  }, [compact])

  useEffect(() => {
    tickRef.current = 0
    readyRef.current = false
    settledRef.current = false
  }, [graphData])

  useEffect(
    () => () => {
      if (pauseTimerRef.current !== null)
        window.clearTimeout(pauseTimerRef.current)
      graphRef.current?.pauseAnimation?.()
      const scene = graphRef.current?.scene?.()
      scene?.traverse((object: THREE.Object3D) => {
        if (object.userData.characterVisual) disposeCharacterObject(object)
      })
    },
    [],
  )

  if (!webglAvailable)
    return <CharacterGraphFallback artifact={artifact} onSelect={onSelect} />

  return (
    <div
      aria-label="人物关系 3D 星图"
      className="phase32-cast-graph-canvas"
      onPointerEnter={() =>
        readyRef.current && graphRef.current?.resumeAnimation?.()
      }
      onPointerLeave={() =>
        settledRef.current && graphRef.current?.pauseAnimation?.()
      }
      ref={containerRef}
      role="region"
    >
      <div
        className="phase32-cast-camera-controls"
        aria-label="3D 星图视角"
        role="group"
      >
        <button
          type="button"
          aria-label="缩小人物星图"
          title="缩小"
          onClick={() => requestCamera("zoom-out")}
        >
          <ZoomOut size={14} />
        </button>
        <button
          type="button"
          aria-label="适配人物星图"
          title="适配全景"
          onClick={() => requestCamera("fit")}
        >
          <Scan size={14} />
        </button>
        <button
          type="button"
          aria-label="放大人物星图"
          title="放大"
          onClick={() => requestCamera("zoom-in")}
        >
          <ZoomIn size={14} />
        </button>
      </div>
      <ForceGraph3D
        ref={graphRef}
        backgroundColor="rgba(0,0,0,0)"
        cooldownTicks={110}
        enableNodeDrag
        graphData={graphData}
        height={size.height}
        linkColor={(link) => {
          const edge = link as CharacterGraphEdge
          return focusId && !relationTouches(edge, focusId)
            ? "#2b2e2c"
            : edge.color
        }}
        linkCurvature={(link) => relationCurve(link as CharacterGraphEdge)}
        linkCurveRotation={(link) =>
          relationCurveRotation(link as CharacterGraphEdge)
        }
        linkDirectionalArrowLength={3.8}
        linkDirectionalArrowRelPos={0.94}
        linkOpacity={0.58}
        linkPositionUpdate={(object, { start, end }) =>
          positionRelationLabel(object, start, end)
        }
        linkThreeObject={(link) => {
          const edge = link as CharacterGraphEdge
          const dimmed = Boolean(focusId && !relationTouches(edge, focusId))
          return createRelationLabel(edge, {
            compact,
            dimmed,
            visible:
              !compact &&
              !dimmed &&
              (graph.links.length <= 7 ||
                relationTouches(edge, selectedId || "")),
          })
        }}
        linkThreeObjectExtend
        linkWidth={(link) => {
          const edge = link as CharacterGraphEdge
          return focusId && !relationTouches(edge, focusId)
            ? 0.35
            : 0.8 + edge.strength * 1.55
        }}
        nodeLabel={(node) =>
          escapeHtml(
            `${(node as CharacterGraphNode).name} · ${(node as CharacterGraphNode).role}`,
          )
        }
        nodeOpacity={0}
        nodeThreeObject={(node) => {
          const item = node as CharacterGraphNode
          const dimmed = Boolean(focusId && !neighborhood.has(item.id))
          const selected = item.id === selectedId || item.id === hoveredId
          return createCharacterNodeObject(item, {
            compact,
            dimmed,
            selected,
            showLabel: selected || (!compact && !dimmed),
          })
        }}
        nodeThreeObjectExtend
        nodeVal={(node) => (node as CharacterGraphNode).val}
        onBackgroundClick={() => onSelect(null)}
        onEngineStop={() => {
          readyRef.current = true
          settledRef.current = true
          const reducedMotion = window.matchMedia(
            "(prefers-reduced-motion: reduce)",
          ).matches
          if (selectedId) focusSubject(selectedId, reducedMotion ? 0 : 360)
          else fitGraph(reducedMotion ? 0 : 460)
          if (pauseTimerRef.current !== null)
            window.clearTimeout(pauseTimerRef.current)
          pauseTimerRef.current = window.setTimeout(
            () => {
              if (!containerRef.current?.matches(":hover"))
                graphRef.current?.pauseAnimation?.()
            },
            reducedMotion ? 0 : 520,
          )
        }}
        onEngineTick={() => {
          readyRef.current = true
          tickRef.current += 1
          if (tickRef.current === 16 && !selectedId)
            fitGraph(
              window.matchMedia("(prefers-reduced-motion: reduce)").matches
                ? 0
                : 420,
            )
        }}
        onNodeClick={(node) => onSelect((node as CharacterGraphNode).id)}
        onNodeHover={(node) =>
          setHoveredId(node ? (node as CharacterGraphNode).id : null)
        }
        showNavInfo={false}
        warmupTicks={38}
        width={size.width}
      />
    </div>
  )
}

function CharacterGraphFallback({
  artifact,
  onSelect,
}: Pick<Props, "artifact" | "onSelect">) {
  return (
    <div className="phase32-cast-graph-fallback" role="status">
      <strong>当前设备无法启用 3D 图谱</strong>
      <span>仍可通过关系目录查看人物连接。</span>
      <div>
        {artifact.relationships.map((relation) => {
          const source = artifact.characters.find(
            (subject) => subject.subject_ref === relation.from_subject_ref,
          )
          const target = artifact.characters.find(
            (subject) => subject.subject_ref === relation.to_subject_ref,
          )
          return (
            <button
              key={`${relation.from_subject_ref}-${relation.to_subject_ref}`}
              type="button"
              onClick={() => onSelect(relation.from_subject_ref)}
            >
              {source?.display_name ?? relation.from_subject_ref} ·{" "}
              {target?.display_name ?? relation.to_subject_ref}
            </button>
          )
        })}
      </div>
    </div>
  )
}

function supportsWebGL() {
  if (
    typeof document === "undefined" ||
    typeof window.WebGLRenderingContext === "undefined"
  )
    return false
  const canvas = document.createElement("canvas")
  const context = canvas.getContext("webgl2") || canvas.getContext("webgl")
  context?.getExtension("WEBGL_lose_context")?.loseContext()
  return Boolean(context)
}

function escapeHtml(value: string) {
  return value.replace(
    /[&<>"']/g,
    (character) => `&#${character.charCodeAt(0)};`,
  )
}
