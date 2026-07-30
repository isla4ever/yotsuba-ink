// Post-build assertion for the CSS entry split (run after `npm run build`):
// 1) no class that exists only in a lazy entry (entry-running / entry-bible) may
//    appear in the first-screen CSS linked from dist/index.html;
// 2) the first-screen CSS must still carry the core shell styles;
// 3) prints raw + gzip sizes for every emitted CSS asset.
import { readFile, readdir } from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { gzipSync } from 'node:zlib';
import postcss from 'postcss';
import { auditCss } from './css-audit-lib.mjs';

const webRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const distDir = path.join(webRoot, 'dist');
const EAGER_ENTRIES = new Set([
  'src/styles/entry-core.css',
]);
const CORE_MARKERS = ['studio-shell', 'product-shell', 'workbench-sidebar'];

function classesOf(cssText) {
  const classes = new Set();
  const root = postcss.parse(cssText);
  root.walkRules((rule) => {
    if (rule.parent?.type === 'atrule' && /keyframes$/i.test(rule.parent.name)) return;
    for (const match of (rule.selector ?? '').matchAll(/\.(-?[A-Za-z_][A-Za-z0-9_-]*)/g)) classes.add(match[1]);
  });
  return classes;
}

const report = await auditCss(webRoot);
const failures = [];

let indexHtml;
try {
  indexHtml = await readFile(path.join(distDir, 'index.html'), 'utf8');
} catch {
  console.error('dist/index.html not found — run `npm run build` first.');
  process.exit(1);
}
const firstScreenHrefs = [...indexHtml.matchAll(/<link[^>]+rel="stylesheet"[^>]+href="([^"]+\.css)"/g)].map((m) => m[1]);
const firstScreenCss = [];
for (const href of firstScreenHrefs) {
  firstScreenCss.push(await readFile(path.join(distDir, href.replace(/^\//, '')), 'utf8'));
}
const firstScreenText = firstScreenCss.join('\n');

// Marker classes: defined in a lazy-entry rule file and nowhere in eager entries.
const eagerClasses = new Set();
const lazyFiles = [];
for (const [entryFile, files] of Object.entries(report.entryImports)) {
  for (const file of files) {
    const text = await readFile(path.join(webRoot, file), 'utf8');
    if (EAGER_ENTRIES.has(entryFile)) {
      for (const cls of classesOf(text)) eagerClasses.add(cls);
    } else {
      lazyFiles.push({ entryFile, file, classes: classesOf(text) });
    }
  }
}
let checkedFiles = 0;
for (const { entryFile, file, classes } of lazyFiles) {
  const marker = [...classes].find((cls) => !eagerClasses.has(cls));
  if (!marker) continue; // every class also exists in an eager file — nothing unique to assert on
  checkedFiles += 1;
  if (new RegExp(`\\.${marker}(?![A-Za-z0-9_-])`).test(firstScreenText)) {
    failures.push(`${file} (${path.basename(entryFile)}) leaked into first-screen CSS via .${marker}`);
  }
}
for (const marker of CORE_MARKERS) {
  if (!new RegExp(`\\.${marker}(?![A-Za-z0-9_-])`).test(firstScreenText)) {
    failures.push(`first-screen CSS is missing core marker .${marker}`);
  }
}

const assetDir = path.join(distDir, 'assets');
const cssAssets = (await readdir(assetDir)).filter((name) => name.endsWith('.css')).sort();
console.log('CSS assets (dist/assets):');
let firstScreenGzip = 0;
for (const name of cssAssets) {
  const buffer = await readFile(path.join(assetDir, name));
  const gzip = gzipSync(buffer, { level: 9 }).length;
  const isFirstScreen = firstScreenHrefs.some((href) => href.endsWith(`/${name}`));
  if (isFirstScreen) firstScreenGzip += gzip;
  console.log(`  ${name}  raw ${buffer.length}  gzip ${gzip}${isFirstScreen ? '  [first screen]' : ''}`);
}
console.log(`First-screen CSS gzip total: ${firstScreenGzip} bytes (${(firstScreenGzip / 1024).toFixed(1)} KiB)`);
console.log(`Lazy-entry rule files asserted absent from first screen: ${checkedFiles}`);

if (failures.length) {
  console.error(`CSS split check failed:\n- ${failures.join('\n- ')}`);
  process.exit(1);
}
console.log('CSS split check passed.');
