export type ChapterRevisionOperation = 'rewrite' | 'expand' | 'compress' | 'restyle';

export type ChapterSelection = {
  start: number;
  end: number;
  text: string;
};

export type ChapterRevisionCandidate = {
  request_id: string;
  chapter_id: string;
  operation: ChapterRevisionOperation;
  operation_label: string;
  direction: string;
  start: number;
  end: number;
  before: string;
  replacement: string;
  preview_content: string;
  base_version: number;
  base_signature: string;
  candidate_signature: string;
};

export type ChapterRevisionBasePayload = {
  workflow_id: string;
  node_id: string;
  chapter_id: string;
  base_version: number;
  base_signature: string;
  persisted_signature: string;
  base_chapter: Record<string, unknown>;
  request_id: string;
};
