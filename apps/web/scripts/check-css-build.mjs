import { readFile, readdir } from "node:fs/promises"
import path from "node:path"
import { fileURLToPath } from "node:url"
import { gzipSync } from "node:zlib"

const webRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..")
const distRoot = path.join(webRoot, "dist")
const indexHtml = await readFile(path.join(distRoot, "index.html"), "utf8")
const hrefs = [...indexHtml.matchAll(/<link[^>]+rel="stylesheet"[^>]+href="([^"]+\.css)"/g)]
  .map((match) => match[1])
const assets = (await readdir(path.join(distRoot, "assets")))
  .filter((name) => name.endsWith(".css"))
  .sort()
const failures = []
let eagerGzip = 0
let eagerCss = ""

for (const href of hrefs) {
  const source = await readFile(path.join(distRoot, href.replace(/^\//, "")))
  eagerGzip += gzipSync(source, { level: 9 }).length
  eagerCss += source.toString("utf8")
}

for (const marker of ["nav-item", "author-collaboration-panel", "stage-candidate-actions"]) {
  if (!new RegExp(`\\.${marker}(?![A-Za-z0-9_-])`).test(eagerCss)) {
    failures.push(`built CSS is missing .${marker}`)
  }
}
if (eagerGzip > 32 * 1024) failures.push(`first-screen CSS gzip ${eagerGzip} exceeds 32 KiB`)

console.log(`CSS assets: ${assets.join(", ")}`)
console.log(`First-screen CSS gzip: ${eagerGzip} bytes (${(eagerGzip / 1024).toFixed(1)} KiB)`)
if (failures.length) {
  console.error(`CSS build check failed:\n- ${failures.join("\n- ")}`)
  process.exit(1)
}
console.log("CSS build check passed.")
