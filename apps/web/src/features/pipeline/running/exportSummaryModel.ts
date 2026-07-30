import type { ExportArtifact } from './stageArtifacts';
import { exportDeliveryReady, normalizeExportValidation } from './exportValidation';

export function exportStageSummary(artifact: ExportArtifact) {
  const chapterCount = artifact.chapters?.length ?? 0;
  const normalized = normalizeExportValidation(artifact.validation, {
    hasChapters: chapterCount > 0,
    hasCoverAsset: Boolean(artifact.cover_asset),
  });
  const validation = Object.values(normalized);
  const readyCount = validation.filter((status) => status === 'ready').length;
  const finalReady = artifact.package_ready && exportDeliveryReady(normalized);
  const description = finalReady
    ? `${chapterCount} 章正文已通过 ${validation.length} 项交付校验，可以生成不可变下载版本。`
    : `${chapterCount} 章正文已进入交付清单，仍有 ${validation.length - readyCount} 项校验未就绪。`;
  return {
    description,
    metrics: [`${chapterCount} 章`, `${readyCount}/${validation.length} 校验`, `${artifact.formats.length} 种格式`],
  };
}
