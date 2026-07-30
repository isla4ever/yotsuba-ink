export type ReferenceSearchResult = {
  title: string;
  url: string;
  content: string;
  score: number;
};

export type ReferenceSearchResponse = {
  enabled: boolean;
  provider: string;
  message: string;
  results: ReferenceSearchResult[];
};

export type KnowledgeSearchResult = {
  doc_id: string;
  chunk_id: string;
  title: string;
  section: string;
  preview: string;
  score: number;
  source_type: string;
  metadata: Record<string, unknown>;
};

export type KnowledgeSearchResponse = {
  backend: string;
  backend_available: boolean;
  query_rewrite: string;
  message: string;
  results: KnowledgeSearchResult[];
};
