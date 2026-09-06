import { readFile, readdir, writeFile } from "node:fs/promises"
import path from "node:path"
import { fileURLToPath } from "node:url"
import postcss from "postcss"

const webRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..")
const sourceRoot = path.join(webRoot, "src")
const entryPath = path.join(webRoot, "src/index.css")
const stylesRoot = path.join(webRoot, "src/styles")
const baselinePath = path.join(webRoot, "scripts/css-audit-baseline.json")
const updateBaseline = process.argv.includes("--update-baseline")
const entrySource = await readFile(entryPath, "utf8")
const entryRoot = postcss.parse(entrySource, { from: entryPath })
const styleFiles = (await readdir(stylesRoot))
  .filter((name) => name.endsWith(".css"))
  .sort()

const importedFiles = []
entryRoot.walkAtRules("import", (rule) => {
  const match = rule.params.match(/^(['"])(.+?)\1/)
  if (!match || !match[2].startsWith("./styles/")) return
  importedFiles.push(path.basename(match[2]))
})

const moduleImportedFiles = []
for (const file of await collectFiles(sourceRoot, /\.(?:ts|tsx)$/)) {
  const source = await readFile(file, "utf8")
  for (const match of source.matchAll(/import\s+["']([^"']+\.css)["']/g)) {
    const resolved = path.resolve(path.dirname(file), match[1])
    if (path.dirname(resolved) === stylesRoot) {
      moduleImportedFiles.push(path.basename(resolved))
    }
  }
}
const ownedFiles = [...importedFiles, ...moduleImportedFiles].sort()

const failures = []
for (const file of styleFiles) {
  const count = ownedFiles.filter((candidate) => candidate === file).length
  if (count !== 1)
    failures.push(`${file} must be imported exactly once; found ${count}`)
}
for (const file of ownedFiles) {
  if (!styleFiles.includes(file))
    failures.push(`missing imported stylesheet: ${file}`)
}

const sources = [
  { name: "src/index.css", source: entrySource },
  ...(await Promise.all(
    styleFiles.map(async (file) => ({
      name: `src/styles/${file}`,
      source: await readFile(path.join(stylesRoot, file), "utf8"),
    })),
  )),
]
const selectors = new Map()
const keyframes = new Map()
let ruleCount = 0
let selectorCount = 0
let infiniteAnimationCount = 0
let reducedMotionGuardCount = 0

for (const { name, source } of sources) {
  const root = postcss.parse(source, { from: path.join(webRoot, name) })
  root.walkAtRules((rule) => {
    if (/keyframes$/i.test(rule.name)) {
      const owners = keyframes.get(rule.params) ?? []
      owners.push(name)
      keyframes.set(rule.params, owners)
    }
    if (
      rule.name === "media" &&
      /prefers-reduced-motion\s*:\s*reduce/i.test(rule.params)
    ) {
      reducedMotionGuardCount += 1
    }
  })
  root.walkDecls((declaration) => {
    if (
      /^animation(?:-|$)/.test(declaration.prop) &&
      /\binfinite\b/i.test(declaration.value)
    ) {
      infiniteAnimationCount += 1
    }
  })
  root.walkRules((rule) => {
    if (insideKeyframes(rule)) return
    ruleCount += 1
    for (const rawSelector of rule.selectors ?? []) {
      selectorCount += 1
      const selector = rawSelector.replace(/\s+/g, " ").trim()
      const owners = selectors.get(selector) ?? new Set()
      owners.add(name)
      selectors.set(selector, owners)
    }
  })
}

const duplicateSelectors = [...selectors]
  .filter(([, owners]) => owners.size > 1)
  .map(([selector, owners]) => ({ selector, files: [...owners] }))
const duplicateKeyframes = [...keyframes]
  .filter(([, owners]) => new Set(owners).size > 1)
  .map(([name, owners]) => ({ name, files: [...new Set(owners)] }))
const metrics = {
  cssBytes: sources.reduce(
    (total, file) => total + Buffer.byteLength(file.source),
    0,
  ),
  sourceLineCount: sources.reduce(
    (total, file) => total + file.source.split(/\r?\n/).length,
    0,
  ),
  ruleCount,
  selectorCount,
  uniqueSelectorCount: selectors.size,
  crossFileDuplicateSelectorCount: duplicateSelectors.length,
  duplicateKeyframeNameCount: duplicateKeyframes.length,
  infiniteAnimationCount,
  reducedMotionGuardCount,
}

if (reducedMotionGuardCount < 1)
  failures.push("a prefers-reduced-motion guard is required")

if (updateBaseline) {
  if (failures.length) fail(failures)
  const baseline = {
    schemaVersion: 1,
    generatedOn: new Date().toISOString().slice(0, 10),
    importedFiles: ownedFiles,
    budgets: metrics,
  }
  await writeFile(baselinePath, `${JSON.stringify(baseline, null, 2)}\n`)
  console.log(`Updated ${path.relative(webRoot, baselinePath)}`)
} else {
  let baseline
  try {
    baseline = JSON.parse(await readFile(baselinePath, "utf8"))
  } catch {
    failures.push(
      "CSS baseline is missing; review and run pnpm audit:css -- --update-baseline",
    )
  }
  if (baseline) {
    if (JSON.stringify(baseline.importedFiles) !== JSON.stringify(ownedFiles)) {
      failures.push(
        "stylesheet import ownership changed; review and update the baseline",
      )
    }
    for (const [metric, value] of Object.entries(metrics)) {
      if (value > baseline.budgets[metric]) {
        failures.push(
          `${metric} ${value} exceeds baseline ${baseline.budgets[metric]}`,
        )
      }
    }
  }
  console.log("CSS audit")
  for (const [metric, value] of Object.entries(metrics))
    console.log(`  ${metric}: ${value}`)
  if (duplicateSelectors.length) {
    console.log("Cross-file duplicate selectors")
    for (const record of duplicateSelectors.slice(0, 12)) {
      console.log(`  ${record.selector}: ${record.files.join(", ")}`)
    }
  }
  if (failures.length) fail(failures)
  console.log("CSS audit passed.")
}

function insideKeyframes(node) {
  for (let parent = node.parent; parent; parent = parent.parent) {
    if (parent.type === "atrule" && /keyframes$/i.test(parent.name)) return true
  }
  return false
}

async function collectFiles(root, pattern) {
  const files = []
  for (const entry of await readdir(root, { withFileTypes: true })) {
    const absolute = path.join(root, entry.name)
    if (entry.isDirectory())
      files.push(...(await collectFiles(absolute, pattern)))
    else if (pattern.test(entry.name)) files.push(absolute)
  }
  return files
}

function fail(items) {
  console.error(`CSS audit failed:\n- ${items.join("\n- ")}`)
  process.exit(1)
}
