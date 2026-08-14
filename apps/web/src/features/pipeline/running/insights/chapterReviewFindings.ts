import type { RunEvent } from '../../contracts';

export type ReviewFinding = {
  claim: string;
  code: string;
  evidence: string;
  severity: 'blocking' | 'advisory' | string;
};

export type ReviewLane = {
  available: boolean;
  chapterId: string;
  findings: ReviewFinding[];
  required: boolean;
  role: string;
};

const roleLabels: Record<string, string> = {
  character: '人物一致性',
  continuity: '连续性',
  prose: '文风',
};

export function reviewRoleLabel(role: string) {
  return roleLabels[role] ?? role ?? '审稿';
}

export function severityLabel(severity: string) {
  return severity === 'blocking' ? '阻断' : severity === 'advisory' ? '建议' : severity;
}

/**
 * Latest review verdict per (chapter, role). Reviewers rerun after a revision,
 * so only the newest lane per role reflects the chapter the author is reading.
 */
export function chapterReviewLanes(events: RunEvent[], chapterId: string): ReviewLane[] {
  const lanes = new Map<string, ReviewLane>();
  const ordered = [...events].sort((left, right) => (left.sequence ?? 0) - (right.sequence ?? 0));
  let newestVersion = '';
  for (const event of ordered) {
    if (event.type !== 'review.completed' && event.type !== 'review.unavailable') continue;
    if (chapterId && event.chapter_id && event.chapter_id !== chapterId) continue;
    const payload = readPayload(event);
    const role = String(payload.role ?? '');
    if (!role) continue;
    // A regenerated chapter reviews a new version under the same chapter id;
    // only the newest version's verdicts describe the draft on screen.
    const version = reviewVersionId(event);
    if (version && version !== newestVersion) {
      newestVersion = version;
      lanes.clear();
    }
    lanes.set(role, {
      available: event.type === 'review.completed' && payload.available !== false,
      chapterId: String(event.chapter_id ?? ''),
      findings: readFindings(payload.findings),
      required: payload.required === true,
      role,
    });
  }
  return [...lanes.values()];
}

export function blockingCount(lanes: ReviewLane[]) {
  return lanes.reduce(
    (total, lane) => total + lane.findings.filter((finding) => finding.severity === 'blocking').length,
    0,
  );
}

/** `run:chapter-1:review:chapter-1-v2:character:completed` carries the version. */
function reviewVersionId(event: RunEvent): string {
  const parts = String(event.event_id ?? '').split(':');
  const marker = parts.indexOf('review');
  return marker >= 0 ? (parts[marker + 1] ?? '') : '';
}

function readPayload(event: RunEvent): Record<string, unknown> {
  const raw = event.payload as unknown;
  if (typeof raw === 'string') {
    try {
      const parsed = JSON.parse(raw);
      return parsed && typeof parsed === 'object' ? (parsed as Record<string, unknown>) : {};
    } catch {
      return {};
    }
  }
  return raw && typeof raw === 'object' ? (raw as Record<string, unknown>) : {};
}

function readFindings(value: unknown): ReviewFinding[] {
  if (!Array.isArray(value)) return [];
  return value.map((item) => {
    const finding = (item ?? {}) as Record<string, unknown>;
    return {
      claim: String(finding.claim ?? ''),
      code: String(finding.code ?? ''),
      evidence: String(finding.evidence ?? ''),
      severity: String(finding.severity ?? 'advisory'),
    };
  });
}
