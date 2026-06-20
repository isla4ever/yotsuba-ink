export type KnowledgeDocument = {
  doc_id: string;
  project_id?: string;
  title: string;
  filename: string;
  content_type?: string;
  char_count?: number;
  chunk_count: number;
  status: string;
  parser: string;
  backend?: string;
  capability_note?: string;
  preview: string;
  created_at?: string;
};

export type KnowledgeDeleteResponse = {
  ok: boolean;
  doc_id: string;
  deleted_chunks?: number;
  backend?: string;
  backend_synced?: boolean;
  message?: string;
};
