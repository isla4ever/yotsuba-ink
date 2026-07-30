import type { QualityReport } from './quality';
import type { ChapterRevisionOperation } from './chapterRevision';

export type ChapterQualityRepairTarget = {
  finding_id: string;
  chapter_id: string;
  chapter: string;
  artifact_signature: string;
  chapter_version: number;
  dimension: string;
  message: string;
  instruction: string;
  operation: ChapterRevisionOperation;
  start: number;
  end: number;
  selected_text: string;
  locatable: boolean;
};

export type ModelReviewDimension = {
  dimension: string;
  score: number;
  evidence?: string;
  revision_instruction?: string;
};

/** Phase 10.4a additive contract: `ChapterItem.model_review` / `model_review_completed` payload.
 *  All fields optional beyond `status` — old runs simply miss the whole object. */
export type ChapterModelReview = {
  status: 'completed' | 'unavailable';
  chapter?: string;
  chapter_version?: number;
  content_signature?: string;
  dimensions?: ModelReviewDimension[];
  overall_score?: number;
  tension?: { score?: number; basis?: string };
  voice?: { drift?: boolean; notes?: string };
  error?: string;
  source?: string;
};

export type ChapterQualityRecheck = {
  status: 'passed' | 'blocked';
  artifact_signature: string;
  chapter_version: number;
  request_id: string;
  report: QualityReport & Record<string, unknown>;
  repair_targets?: ChapterQualityRepairTarget[];
};

export type CanonConflict = {
  id: string;
  status: 'pending' | 'resolved';
  target: string;
  claim_key: string;
  existing_fact_id?: string;
  existing_fact: string;
  incoming_candidate_id?: string;
  incoming_fact: string;
  resolution?: 'keep_existing' | 'replace_existing';
};

export type CanonPreview = {
  candidates: Array<Record<string, unknown>>;
  conflicts: CanonConflict[];
};

export type ChapterWritebackProposal = {
  id: string;
  chapter_id: string;
  chapter: string;
  version: number;
  artifact_signature: string;
  proposal_signature: string;
  status: 'pending' | 'accepted' | 'rejected' | 'blocked' | 'not_required';
  wiki_writebacks: Array<Record<string, unknown>>;
  character_shift: unknown;
  foreshadow_updates: Array<Record<string, unknown>>;
  counts: {
    wiki: number;
    character: number;
    foreshadow: number;
  };
  canon?: CanonPreview;
  conflict_resolutions?: Record<string, 'keep_existing' | 'replace_existing'>;
  created_at: string;
  decided_at?: string;
};

export type ChapterReviewResponse = {
  artifact: unknown;
  chapter: Record<string, unknown>;
  events?: Array<Record<string, unknown>>;
  quality_report?: QualityReport;
  proposal?: ChapterWritebackProposal;
};
