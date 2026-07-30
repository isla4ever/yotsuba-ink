import { readFile, writeFile } from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { auditCss, MONOTONIC_METRICS } from './css-audit-lib.mjs';

const webRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const baselinePath = path.join(webRoot, 'scripts/css-audit-baseline.json');
const updateBaseline = process.argv.includes('--update-baseline');
const jsonOnly = process.argv.includes('--json');
const report = await auditCss(webRoot);

function structuralFailures() {
  const failures = [];
  for (const [name, files] of Object.entries(report.integrity)) {
    if (files.length) failures.push(`${name}: ${files.join(', ')}`);
  }
  const unowned = report.files.filter((file) => !file.owner).map((file) => file.path);
  if (unowned.length) failures.push(`unownedFiles: ${unowned.join(', ')}`);
  return failures;
}

function createBaseline() {
  return {
    schemaVersion: 2,
    generatedOn: new Date().toISOString().slice(0, 10),
    entryFiles: report.entryFiles,
    budgets: Object.fromEntries(MONOTONIC_METRICS.map((metric) => [metric, report.metrics[metric]])),
    minimums: { globalReducedMotionGuardCount: Math.max(1, report.metrics.globalReducedMotionGuardCount) },
    importedFiles: report.files.map((file) => file.path),
    ownership: Object.fromEntries(report.files.map((file) => [file.path, file.owner])),
    entryAssignments: Object.fromEntries(report.files.map((file) => [file.path, file.entry])),
  };
}

function printReport() {
  console.log('CSS audit');
  for (const [metric, value] of Object.entries(report.metrics)) console.log(`  ${metric}: ${value}`);
  console.log('Entries');
  for (const entryFile of report.entryFiles) console.log(`  ${entryFile}: ${report.entryImports[entryFile].length} files`);
  const ownerCounts = report.files.reduce((groups, file) => {
    (groups[file.owner] ??= []).push(file);
    return groups;
  }, {});
  console.log('Owners');
  for (const [owner, files] of Object.entries(ownerCounts).sort()) console.log(`  ${owner}: ${files.length}`);
  console.log('Top cross-file duplicate selectors');
  for (const item of report.duplicateSelectors.slice(0, 15)) {
    console.log(`  ${item.selector} -> ${item.owners.map((owner) => owner.path).join(', ')}`);
  }
}

const failures = structuralFailures();
if (updateBaseline) {
  if (failures.length) {
    console.error(`Cannot update CSS baseline:\n- ${failures.join('\n- ')}`);
    process.exitCode = 1;
  } else {
    await writeFile(baselinePath, `${JSON.stringify(createBaseline(), null, 2)}\n`);
    console.log(`Updated ${path.relative(webRoot, baselinePath)}`);
  }
} else {
  let baseline;
  try {
    baseline = JSON.parse(await readFile(baselinePath, 'utf8'));
  } catch {
    failures.push('baselineMissing: run npm run audit:css -- --update-baseline after reviewing the report');
  }
  if (baseline) {
    for (const metric of MONOTONIC_METRICS) {
      if (report.metrics[metric] > baseline.budgets[metric]) {
        failures.push(`${metric}: ${report.metrics[metric]} exceeds baseline ${baseline.budgets[metric]}`);
      }
    }
    for (const [metric, minimum] of Object.entries(baseline.minimums)) {
      if (report.metrics[metric] < minimum) failures.push(`${metric}: ${report.metrics[metric]} is below minimum ${minimum}`);
    }
    const knownEntries = new Set(baseline.entryFiles ?? []);
    const unexpectedEntries = report.entryFiles.filter((file) => !knownEntries.has(file));
    if (unexpectedEntries.length) failures.push(`newEntryFilesNeedReview: ${unexpectedEntries.join(', ')}`);
    const knownFiles = new Set(baseline.importedFiles);
    const unexpectedFiles = report.files.filter((file) => !knownFiles.has(file.path)).map((file) => file.path);
    if (unexpectedFiles.length) failures.push(`newImportedFilesNeedReview: ${unexpectedFiles.join(', ')}`);
    for (const file of report.files) {
      if (baseline.ownership[file.path] && baseline.ownership[file.path] !== file.owner) {
        failures.push(`ownerChanged: ${file.path} (${baseline.ownership[file.path]} -> ${file.owner})`);
      }
      const baselineEntry = baseline.entryAssignments?.[file.path];
      if (baselineEntry && baselineEntry !== file.entry) {
        failures.push(`entryChanged: ${file.path} (${baselineEntry} -> ${file.entry})`);
      }
    }
  }
  if (jsonOnly) console.log(JSON.stringify({ ...report, failures }, null, 2));
  else printReport();
  if (failures.length) {
    console.error(`CSS audit failed:\n- ${failures.join('\n- ')}`);
    process.exitCode = 1;
  } else if (!jsonOnly) {
    console.log('CSS audit passed.');
  }
}
