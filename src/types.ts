export type Role = "user" | "assistant";

export interface Source {
  citation: number;
  chunk_id: number;
  title: string;
  source: string;
  url?: string | null;
  excerpt: string;
  retrieval_score: number;
  rerank_score?: number | null;
}

export interface Message {
  id: string;
  role: Role;
  content: string;
  sources?: Source[];
  createdAt: string;
  error?: boolean;
}

export interface ChatRequest {
  message: string;
  history: Array<{ role: Role; content: string }>;
}

export interface ChatResponse {
  answer: string;
  sources: Source[];
  model: string;
  retrieved_count: number;
  reranked: boolean;
}

export interface HealthResponse {
  status: "ready" | "degraded";
  rag_ready: boolean;
  gemini_ready: boolean;
  reranker_ready: boolean;
  detail?: string | null;
}
