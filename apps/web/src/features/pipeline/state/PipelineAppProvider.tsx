import {
  createContext,
  useCallback,
  useContext,
  useState,
  useEffect,
  useRef,
  type ReactNode,
} from "react"
import type { Route, Mode, Theme, Project } from "../contracts/app"
import type {
  ChapterVersionRecord,
  GraphRunEnvelope,
  NarrativeStageId,
  RunArtifactRecord,
  RunEvent,
} from "../contracts/run"
import type { RunConnectionState } from "./useActiveRun"
import {
  pathForRoute,
  projectIdFromLocation,
  routeFromLocation,
  templateIdFromLocation,
} from "../lib/routes"
import { projectPresentation } from "../lib/projectPresentation"
import { getProjectSummary } from "../services/projectApi"
import { getWorkflowDefinition } from "../services/workflowApi"
import { useActiveRun } from "./useActiveRun"
import { useRunArtifacts } from "./useRunArtifacts"

interface AppCtx {
  route: Route
  setRoute: (r: Route) => void
  theme: Theme
  toggleTheme: () => void
  mode: Mode
  setMode: (m: Mode) => void
  sidebarCollapsed: boolean
  toggleSidebar: () => void
  cmdOpen: boolean
  setCmdOpen: (v: boolean) => void
  selectedChapter: string
  setSelectedChapter: (id: string) => void
  selectedChar: string | null
  setSelectedChar: (id: string | null) => void
  /* Project open/close */
  projectOpen: boolean
  projectLoading: boolean
  activeProjectId: string | null
  activeProject: Project | null
  activeRun: GraphRunEnvelope | null
  runConnection: RunConnectionState
  runError: string
  runEvents: RunEvent[]
  runLoading: boolean
  runArtifactLoading: boolean
  runArtifactError: string
  runArtifacts: Partial<Record<NarrativeStageId, RunArtifactRecord>>
  runCandidateArtifacts: Partial<Record<NarrativeStageId, RunArtifactRecord>>
  runChapters: ChapterVersionRecord[]
  acceptedRunChapters: ChapterVersionRecord[]
  refreshRun: () => Promise<GraphRunEnvelope | null>
  openProject: (project: Project, startRoute?: Route) => void
  closeProject: () => void
  mobileDrawerOpen: boolean
  setMobileDrawerOpen: (v: boolean) => void
  /* Workflow template selection (wizard pre-select) */
  selectedTemplateId: string | null
  setSelectedTemplateId: (id: string | null) => void
  /* Spine workbench selection */
  spineSelectedId: string
  setSpineSelectedId: (id: string) => void
  /* Volume workbench selection */
  selectedVolumeId: string
  setSelectedVolumeId: (id: string) => void
}

const Ctx = createContext<AppCtx | null>(null)

export function useApp() {
  const ctx = useContext(Ctx)
  if (!ctx) throw new Error("useApp must be used inside AppProvider")
  return ctx
}

export function AppProvider({ children }: { children: ReactNode }) {
  const [route, setRouteState] = useState<Route>(() =>
    routeFromLocation(window.location),
  )
  const [theme, setTheme] = useState<Theme>("dark")
  const [mode, setModeState] = useState<Mode>("balanced")
  const modeRef = useRef<Mode>("balanced")
  const modeTransitionTimerRef = useRef<ReturnType<typeof setTimeout> | null>(
    null,
  )
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false)
  const [cmdOpen, setCmdOpen] = useState(false)
  const [selectedChapter, setSelectedChapter] = useState("ch-001")
  const [selectedChar, setSelectedChar] = useState<string | null>("char-001")
  const initialProjectId = projectIdFromLocation(window.location)
  const initialTemplateId = templateIdFromLocation(window.location)
  const [projectOpen, setProjectOpen] = useState(Boolean(initialProjectId))
  const [projectLoading, setProjectLoading] = useState(
    Boolean(initialProjectId),
  )
  const [activeProjectId, setActiveProjectId] = useState<string | null>(
    initialProjectId,
  )
  const activeProjectIdRef = useRef<string | null>(initialProjectId)
  const [activeProject, setActiveProject] = useState<Project | null>(null)
  const [mobileDrawerOpen, setMobileDrawerOpen] = useState(false)
  const [selectedTemplateId, setSelectedTemplateIdState] =
    useState<string | null>(initialTemplateId)
  const selectedTemplateIdRef = useRef<string | null>(initialTemplateId)
  const [spineSelectedId, setSpineSelectedId] = useState("")
  const [selectedVolumeId, setSelectedVolumeId] = useState("")
  const activeRunState = useActiveRun(activeProject?.latestRunId || null)
  const latestCommittedChapterEvent = activeRunState.events
    .filter(
      (event) =>
        event.type === "artifact.committed" && event.stage_id === "text",
    )
    .reduce((latest, event) => Math.max(latest, event.sequence), 0)
  const activeArtifactState = useRunArtifacts(
    activeRunState.envelope,
    latestCommittedChapterEvent,
  )

  const setMode = useCallback((nextMode: Mode) => {
    if (modeRef.current === nextMode) return
    modeRef.current = nextMode
    document.documentElement.classList.add("mode-switching")
    setModeState(nextMode)
    if (modeTransitionTimerRef.current)
      clearTimeout(modeTransitionTimerRef.current)
    modeTransitionTimerRef.current = setTimeout(() => {
      document.documentElement.classList.remove("mode-switching")
      modeTransitionTimerRef.current = null
    }, 200)
  }, [])

  const setSelectedTemplateId = useCallback((workflowId: string | null) => {
    selectedTemplateIdRef.current = workflowId
    setSelectedTemplateIdState(workflowId)
  }, [])

  const setRoute = useCallback((nextRoute: Route) => {
    setRouteState(nextRoute)
    window.history.pushState(
      null,
      "",
      pathForRoute(
        nextRoute,
        activeProjectIdRef.current,
        selectedTemplateIdRef.current,
      ),
    )
  }, [])

  const openProject = (
    project: Project,
    startRoute: Route = project.currentStage,
  ) => {
    setActiveProject(project)
    setActiveProjectId(project.id)
    activeProjectIdRef.current = project.id
    setProjectOpen(true)
    setProjectLoading(false)
    setRouteState(startRoute)
    window.history.pushState(null, "", pathForRoute(startRoute, project.id))
    setMobileDrawerOpen(false)
  }

  const closeProject = () => {
    setProjectOpen(false)
    setProjectLoading(false)
    setActiveProjectId(null)
    activeProjectIdRef.current = null
    setActiveProject(null)
    setRouteState("studio")
    window.history.pushState(null, "", "/studio")
    setMobileDrawerOpen(false)
  }

  useEffect(() => {
    const syncLocation = () => {
      const nextProjectId = projectIdFromLocation(window.location)
      setRouteState(routeFromLocation(window.location))
      setActiveProjectId(nextProjectId)
      activeProjectIdRef.current = nextProjectId
      setProjectOpen(Boolean(nextProjectId))
      const nextTemplateId = templateIdFromLocation(window.location)
      selectedTemplateIdRef.current = nextTemplateId
      setSelectedTemplateIdState(nextTemplateId)
    }
    window.addEventListener("popstate", syncLocation)
    return () => window.removeEventListener("popstate", syncLocation)
  }, [])

  useEffect(() => {
    if (!activeProjectId || activeProject?.id === activeProjectId) {
      setProjectLoading(false)
      return
    }
    const controller = new AbortController()
    setProjectLoading(true)
    void getProjectSummary(activeProjectId, controller.signal)
      .then((summary) =>
        setActiveProject(projectPresentation(summary.project, summary)),
      )
      .catch(() => undefined)
      .finally(() => {
        if (!controller.signal.aborted) setProjectLoading(false)
      })
    return () => controller.abort()
  }, [activeProject, activeProjectId])

  useEffect(() => {
    if (activeRunState.envelope) {
      setMode(activeRunState.envelope.definition.quality_mode)
      return
    }
    if (activeProject?.latestRunId) return
    if (!activeProject?.workflowId) return
    const controller = new AbortController()
    void getWorkflowDefinition(activeProject.workflowId, controller.signal)
      .then((workflow) => setMode(workflow.quality_mode))
      .catch(() => undefined)
    return () => controller.abort()
  }, [
    activeProject?.latestRunId,
    activeProject?.workflowId,
    activeRunState.envelope,
    setMode,
  ])

  useEffect(() => {
    document.documentElement.classList.toggle("dark", theme === "dark")
  }, [theme])

  useEffect(() => {
    document.documentElement.setAttribute("data-mode", mode)
  }, [mode])

  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key === "k") {
        e.preventDefault()
        setCmdOpen((prev) => !prev)
      }
      if (e.key === "Escape") {
        setCmdOpen(false)
      }
    }
    window.addEventListener("keydown", handler)
    return () => window.removeEventListener("keydown", handler)
  }, [])

  useEffect(
    () => () => {
      if (modeTransitionTimerRef.current)
        clearTimeout(modeTransitionTimerRef.current)
    },
    [],
  )

  const toggleTheme = () => setTheme((t) => (t === "light" ? "dark" : "light"))
  const toggleSidebar = () => setSidebarCollapsed((c) => !c)

  return (
    <Ctx.Provider
      value={{
        route,
        setRoute,
        theme,
        toggleTheme,
        mode,
        setMode,
        sidebarCollapsed,
        toggleSidebar,
        cmdOpen,
        setCmdOpen,
        selectedChapter,
        setSelectedChapter,
        selectedChar,
        setSelectedChar,
        projectOpen,
        projectLoading,
        activeProjectId,
        activeProject,
        openProject,
        closeProject,
        activeRun: activeRunState.envelope,
        runConnection: activeRunState.connection,
        runError: activeRunState.error,
        runEvents: activeRunState.events,
        runLoading: activeRunState.loading,
        runArtifactLoading: activeArtifactState.loading,
        runArtifactError: activeArtifactState.error,
        runArtifacts: activeArtifactState.artifacts,
        runCandidateArtifacts: activeArtifactState.candidateArtifacts,
        runChapters: activeArtifactState.chapters,
        acceptedRunChapters: activeArtifactState.acceptedChapters,
        refreshRun: () => activeRunState.refresh(),
        mobileDrawerOpen,
        setMobileDrawerOpen,
        selectedTemplateId,
        setSelectedTemplateId,
        spineSelectedId,
        setSpineSelectedId,
        selectedVolumeId,
        setSelectedVolumeId,
      }}
    >
      {children}
    </Ctx.Provider>
  )
}
