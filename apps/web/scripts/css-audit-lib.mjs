import { readFile, readdir } from 'node:fs/promises';
import path from 'node:path';
import postcss from 'postcss';

const OWNER_RULES = [
  ['design-system', /^(design-tokens|foundation|forms-and-docs|option-field|keyframes-and-responsive|control-state-system|loading-indicators|loading-overlays|motion-reveal|accessibility-responsive-closure)\.css$/],
  ['layout-shell', /^(header-|history-|knowledge-rail|inspector-reference|dialogs|overlay-feedback-system|unsaved-draft-guard|destructive-action-safety|product-navigation|workbench-sidebar|command-palette|global-tool-dock|quality-mode-transition)/],
  ['studio', /^studio-/],
  ['planning', /^(planning-|guided-setup|artifact-deck|narrative-profiles|book-scale-target)/],
  ['story-bible', /^story-bible/],
  ['settings', /^settings-/],
  ['stage-info', /^stage-run-info-/],
  ['stage-summary', /^(stage-run-summary-|stage-run-artifact-workbench-v[36]-summary)/],
  ['stage-outline', /^(stage-run-outline-|stage-run-volume-chapters|stage-run-artifact-workbench-v3-outline)/],
  ['stage-detail', /^(stage-run-detail-|stage-run-artifact-workbench-v6-outline-detail)/],
  ['stage-writing', /^(stage-run-writing-|stage-run-chapter-revision)/],
  ['stage-cover', /^(stage-run-cover-|stage-run-artifact-workbench-v6-cover)/],
  ['stage-export', /^(stage-run-export-|stage-run-delivery|stage-run-artifact-workbench-v[36]-delivery)/],
  ['stage-shared', /^(stage-artifact-state|stage-run-)/],
  ['run-monitor', /^run-monitor-/],
];

// Loading structure: rule files are grouped into entry manifests (src/styles/entry-*.css).
// entry-core is imported by src/main.tsx; the other entries are imported by their
// workbench components so Vite splits lazy-route CSS out of the first screen.
const ENTRY_PATTERN = /^entry-[a-z0-9-]+\.css$/;

export const MONOTONIC_METRICS = [
  'importedFileCount',
  'cssBytes',
  'sourceLineCount',
  'ruleCount',
  'selectorCount',
  'uniqueSelectorCount',
  'crossFileDuplicateSelectorCount',
  'crossFileDuplicateSelectorOccurrences',
  'keyframeCount',
  'duplicateKeyframeNameCount',
  'animationDeclarationCount',
  'infiniteAnimationDeclarationCount',
];

function normalizePath(value) {
  return value.split(path.sep).join('/');
}

function ownerFor(file) {
  const basename = path.basename(file);
  return OWNER_RULES.find(([, pattern]) => pattern.test(basename))?.[0] ?? '';
}

function isWithinKeyframes(node) {
  for (let parent = node.parent; parent; parent = parent.parent) {
    if (parent.type === 'atrule' && /keyframes$/i.test(parent.name)) return true;
  }
  return false;
}

function isWithinReducedMotion(node) {
  for (let parent = node.parent; parent; parent = parent.parent) {
    if (parent.type === 'atrule' && parent.name === 'media' && /prefers-reduced-motion\s*:\s*reduce/i.test(parent.params)) return true;
  }
  return false;
}

function normalizeSelector(selector) {
  return selector.replace(/\s+/g, ' ').trim();
}

function parseImport(rule, entryDir, webRoot) {
  const match = rule.params.match(/^(['"])(.+?)\1/);
  if (!match || /^(?:https?:|data:)/i.test(match[2])) return '';
  return normalizePath(path.relative(webRoot, path.resolve(entryDir, match[2])));
}

async function readEntryManifest(webRoot, entryFile) {
  const absolute = path.join(webRoot, entryFile);
  const root = postcss.parse(await readFile(absolute, 'utf8'), { from: absolute });
  const imports = [];
  let hasNonImportContent = false;
  root.walkAtRules((rule) => {
    if (rule.name !== 'import') hasNonImportContent = true;
  });
  root.walkRules(() => { hasNonImportContent = true; });
  root.walkAtRules('import', (rule) => {
    const imported = parseImport(rule, path.dirname(absolute), webRoot);
    if (imported) imports.push(imported);
  });
  return { imports, hasNonImportContent };
}

// Every relative CSS import in application code must target an entry manifest
// (package CSS such as @xyflow is out of audit scope); rule files load only via entries.
async function collectCodeCssImports(webRoot) {
  const found = [];
  const stack = ['src'];
  while (stack.length) {
    const dir = stack.pop();
    for (const item of await readdir(path.join(webRoot, dir), { withFileTypes: true })) {
      const rel = `${dir}/${item.name}`;
      if (item.isDirectory()) { stack.push(rel); continue; }
      if (!/\.(ts|tsx)$/.test(item.name)) continue;
      const source = await readFile(path.join(webRoot, rel), 'utf8');
      for (const match of source.matchAll(/import\s+(['"])([^'"]+\.css)\1/g)) {
        if (!match[2].startsWith('.')) continue;
        const resolved = normalizePath(path.relative(webRoot, path.resolve(webRoot, path.dirname(rel), match[2])));
        found.push({ importer: rel, target: resolved });
      }
    }
  }
  return found;
}

async function collectFileMetrics(webRoot, file, entry) {
  const absolute = path.join(webRoot, file);
  const source = await readFile(absolute, 'utf8');
  const root = postcss.parse(source, { from: absolute });
  const selectors = new Map();
  const keyframes = [];
  let animationDeclarationCount = 0;
  let infiniteAnimationDeclarationCount = 0;
  let reducedMotionMediaCount = 0;
  let globalReducedMotionGuardCount = 0;
  let ruleCount = 0;

  root.walkAtRules((rule) => {
    if (/keyframes$/i.test(rule.name)) keyframes.push(rule.params.trim());
    if (rule.name === 'media' && /prefers-reduced-motion\s*:\s*reduce/i.test(rule.params)) reducedMotionMediaCount += 1;
  });
  root.walkDecls((declaration) => {
    const property = declaration.prop.replace(/^-(?:webkit|moz|o)-/, '').toLowerCase();
    if (property === 'animation' || property === 'animation-name' || property === 'animation-iteration-count') {
      animationDeclarationCount += 1;
      if (/\binfinite\b/i.test(declaration.value)) infiniteAnimationDeclarationCount += 1;
    }
  });
  root.walkRules((rule) => {
    if (isWithinKeyframes(rule)) return;
    ruleCount += 1;
    for (const rawSelector of rule.selectors ?? []) {
      const selector = normalizeSelector(rawSelector);
      const record = selectors.get(selector) ?? { count: 0, lines: [] };
      record.count += 1;
      if (rule.source?.start?.line) record.lines.push(rule.source.start.line);
      selectors.set(selector, record);
    }
    if (!isWithinReducedMotion(rule)) return;
    const selectorSet = new Set((rule.selectors ?? []).map(normalizeSelector));
    const declarations = new Map();
    rule.walkDecls((declaration) => declarations.set(declaration.prop, `${declaration.value}${declaration.important ? ' !important' : ''}`));
    if (
      selectorSet.has('*') && selectorSet.has('*::before') && selectorSet.has('*::after')
      && /^none\s*!important$/i.test(declarations.get('animation') ?? '')
      && /^0s\s*!important$/i.test(declarations.get('transition-duration') ?? '')
    ) globalReducedMotionGuardCount += 1;
  });

  return {
    animationDeclarationCount,
    bytes: Buffer.byteLength(source),
    entry,
    globalReducedMotionGuardCount,
    infiniteAnimationDeclarationCount,
    keyframes,
    lines: source.split(/\r?\n/).length,
    owner: ownerFor(file),
    path: file,
    reducedMotionMediaCount,
    ruleCount,
    selectors,
  };
}

export async function auditCss(webRoot) {
  const styleDirNames = (await readdir(path.join(webRoot, 'src/styles'), { withFileTypes: true }))
    .filter((entry) => entry.isFile() && entry.name.endsWith('.css'))
    .map((entry) => entry.name)
    .sort();
  const entryFiles = styleDirNames.filter((name) => ENTRY_PATTERN.test(name)).map((name) => `src/styles/${name}`);
  const styleFiles = styleDirNames.filter((name) => !ENTRY_PATTERN.test(name)).map((name) => `src/styles/${name}`);

  const entryImports = {};
  const entriesWithRules = [];
  for (const entryFile of entryFiles) {
    const manifest = await readEntryManifest(webRoot, entryFile);
    entryImports[entryFile] = manifest.imports;
    if (manifest.hasNonImportContent) entriesWithRules.push(entryFile);
  }
  const imports = entryFiles.flatMap((entryFile) => entryImports[entryFile]);
  const entryOf = new Map();
  const importCounts = new Map();
  for (const entryFile of entryFiles) {
    for (const file of entryImports[entryFile]) {
      importCounts.set(file, (importCounts.get(file) ?? 0) + 1);
      if (!entryOf.has(file)) entryOf.set(file, entryFile);
    }
  }
  const styleFileSet = new Set(styleFiles);
  const entryFileSet = new Set(entryFiles);
  const codeCssImports = await collectCodeCssImports(webRoot);
  const codeImportedEntries = new Set(codeCssImports.filter(({ target }) => entryFileSet.has(target)).map(({ target }) => target));
  const integrity = {
    duplicateImports: [...importCounts].filter(([, count]) => count > 1).map(([file]) => file),
    missingFromEntry: styleFiles.filter((file) => !entryOf.has(file)),
    missingOnDisk: [...new Set(imports)].filter((file) => !styleFileSet.has(file)),
    entriesWithRules,
    ruleFilesImportedFromCode: [...new Set(codeCssImports
      .filter(({ target }) => target.startsWith('src/styles/') && !entryFileSet.has(target))
      .map(({ importer, target }) => `${target} (from ${importer})`))],
    entriesWithoutCodeImporter: entryFiles.filter((entryFile) => !codeImportedEntries.has(entryFile)),
  };

  const files = [];
  for (const file of [...new Set(imports)].filter((candidate) => styleFileSet.has(candidate))) {
    files.push(await collectFileMetrics(webRoot, file, entryOf.get(file)));
  }

  const selectorOwners = new Map();
  const keyframeOwners = new Map();
  for (const file of files) {
    for (const [selector, record] of file.selectors) {
      const owners = selectorOwners.get(selector) ?? [];
      owners.push({ count: record.count, lines: record.lines, path: file.path });
      selectorOwners.set(selector, owners);
    }
    for (const name of file.keyframes) {
      const owners = keyframeOwners.get(name) ?? [];
      owners.push(file.path);
      keyframeOwners.set(name, owners);
    }
  }
  const duplicateSelectors = [...selectorOwners]
    .filter(([, owners]) => owners.length > 1)
    .map(([selector, owners]) => ({ occurrences: owners.reduce((sum, owner) => sum + owner.count, 0), owners, selector }))
    .sort((left, right) => right.owners.length - left.owners.length || right.occurrences - left.occurrences || left.selector.localeCompare(right.selector));
  const duplicateKeyframes = [...keyframeOwners]
    .filter(([, owners]) => owners.length > 1)
    .map(([name, owners]) => ({ name, owners }));
  const sum = (key) => files.reduce((total, file) => total + file[key], 0);
  const metrics = {
    animationDeclarationCount: sum('animationDeclarationCount'),
    crossFileDuplicateSelectorCount: duplicateSelectors.length,
    crossFileDuplicateSelectorOccurrences: duplicateSelectors.reduce((total, item) => total + item.occurrences, 0),
    cssBytes: sum('bytes'),
    duplicateKeyframeNameCount: duplicateKeyframes.length,
    globalReducedMotionGuardCount: sum('globalReducedMotionGuardCount'),
    importedFileCount: files.length,
    infiniteAnimationDeclarationCount: sum('infiniteAnimationDeclarationCount'),
    keyframeCount: files.reduce((total, file) => total + file.keyframes.length, 0),
    reducedMotionMediaCount: sum('reducedMotionMediaCount'),
    ruleCount: sum('ruleCount'),
    selectorCount: files.reduce((total, file) => total + [...file.selectors.values()].reduce((subtotal, value) => subtotal + value.count, 0), 0),
    sourceLineCount: sum('lines'),
    uniqueSelectorCount: selectorOwners.size,
  };

  return {
    duplicateKeyframes,
    duplicateSelectors,
    entryFiles,
    entryImports,
    files: files.map(({ selectors, keyframes, ...file }) => ({ ...file, keyframeCount: keyframes.length, selectorCount: selectors.size })),
    imports,
    integrity,
    metrics,
  };
}
