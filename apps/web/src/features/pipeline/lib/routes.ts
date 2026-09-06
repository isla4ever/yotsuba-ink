import type {
  ProductionStageRoute,
  Route,
} from "@/features/pipeline/contracts/app"

const stageRoutes = new Set<ProductionStageRoute>([
  "brief",
  "cast",
  "beat_board",
  "scene_deck",
  "script",
  "story_map",
  "section_plan",
  "book_architecture",
  "volumes",
  "rolling_detail",
  "text",
  "cover",
  "export",
])

export function routeFromLocation(location: Pick<Location, "pathname">): Route {
  const path = location.pathname.replace(/\/+$/, "") || "/studio"
  if (path === "/studio") return "studio"
  if (path === "/studio/workflows") return "workflow-templates"
  if (path.startsWith("/studio/workflows/")) return "workflow-template-detail"
  if (path === "/studio/new") return "planning"
  if (path === "/history") return "history"
  if (path === "/settings") return "settings"
  if (path === "/settings/project") return "book-settings"
  if (path === "/monitor") return "run-monitor"
  if (path.startsWith("/bible/")) return "story-bible"
  if (path === "/knowledge") return "knowledge"
  if (path.startsWith("/run/")) {
    const stage = path.slice("/run/".length)
    if (isProductionStageRoute(stage)) return stage
  }
  return "studio"
}

export function projectIdFromLocation(
  location: Pick<Location, "search">,
): string | null {
  return new URLSearchParams(location.search).get("project")
}

export function templateIdFromLocation(
  location: Pick<Location, "pathname">,
): string | null {
  const match = location.pathname.match(/^\/studio\/workflows\/([^/]+)$/)
  return match ? decodeURIComponent(match[1]) : null
}

export function pathForRoute(
  route: Route,
  projectId: string | null,
  templateId?: string | null,
): string {
  const projectQuery = projectId
    ? `?project=${encodeURIComponent(projectId)}`
    : ""
  if (route === "studio") return "/studio"
  if (route === "workflow-templates") return "/studio/workflows"
  if (route === "workflow-template-detail")
    return `/studio/workflows/${encodeURIComponent(templateId || "default")}`
  if (route === "planning") return "/studio/new"
  if (route === "history") return "/history"
  if (route === "settings") return "/settings"
  if (route === "book-settings") return `/settings/project${projectQuery}`
  if (route === "run-monitor") return `/monitor${projectQuery}`
  if (route === "story-bible") return `/bible/overview${projectQuery}`
  if (route === "knowledge") return `/knowledge${projectQuery}`
  if (isProductionStageRoute(route)) return `/run/${route}${projectQuery}`
  return "/studio"
}

export function isProductionStageRoute(
  value: string,
): value is ProductionStageRoute {
  return stageRoutes.has(value as ProductionStageRoute)
}
