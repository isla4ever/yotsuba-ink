import { readdir, readFile } from "node:fs/promises"
import path from "node:path"
import { fileURLToPath } from "node:url"

const webRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..")
const sourceRoot = path.join(webRoot, "src")
const pipelineRoot = path.join(sourceRoot, "features/pipeline")
const allowed = new Set([
  "brief",
  "contracts",
  "layout",
  "lib",
  "planning",
  "running",
  "services",
  "settings",
  "state",
])
const forbiddenRootDirectories = new Set(["components", "data", "views"])
const failures = []

for (const entry of await readdir(sourceRoot, { withFileTypes: true })) {
  if (entry.isDirectory() && forbiddenRootDirectories.has(entry.name)) {
    failures.push(`legacy source directory remains: src/${entry.name}`)
  }
}
for (const entry of await readdir(pipelineRoot, { withFileTypes: true })) {
  if (entry.isDirectory() && !allowed.has(entry.name)) {
    failures.push(`unexpected pipeline directory: ${entry.name}`)
  }
}

const sourceFiles = await collectSourceFiles(sourceRoot)
for (const file of sourceFiles) {
  const source = await readFile(file, "utf8")
  if (
    /from\s+["'][^"']*(?:\/components\/|\/views\/|\/context["']|\/types["'])/.test(
      source,
    )
  ) {
    failures.push(`legacy import boundary: ${path.relative(webRoot, file)}`)
  }
  if (/\b(?:mockData|demoData|fakeProgress)\b/.test(source)) {
    failures.push(`production mock marker: ${path.relative(webRoot, file)}`)
  }
}

if (failures.length) {
  console.error(`Structure audit failed:\n- ${failures.join("\n- ")}`)
  process.exit(1)
}
console.log(
  `Structure audit passed (${sourceFiles.length} TypeScript source files).`,
)

async function collectSourceFiles(root) {
  const files = []
  const entries = await readdir(root, { withFileTypes: true })
  for (const entry of entries) {
    const absolute = path.join(root, entry.name)
    if (entry.isDirectory()) files.push(...(await collectSourceFiles(absolute)))
    else if (
      /\.(?:ts|tsx)$/.test(entry.name) &&
      !entry.name.endsWith(".test.ts") &&
      !entry.name.endsWith(".test.tsx")
    )
      files.push(absolute)
  }
  return files
}
