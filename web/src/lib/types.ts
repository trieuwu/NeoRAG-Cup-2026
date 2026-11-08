// Hợp đồng với app/api.py (xem README mục 6). Tên trường giữ nguyên như backend trả về.

export type StageName = 'rewrite' | 'retrieve' | 'rerank' | 'generate'
export const STAGES: StageName[] = ['rewrite', 'retrieve', 'rerank', 'generate']

export interface StageEvent {
  name: StageName
  status: 'start' | 'done'
  ms?: number
}

export interface IncidentEvent {
  type: 'retry' | 'fallback'
  stage: StageName | string | null
  attempt: number | null
  wait_s: number | null
  error?: string
}

export interface Citation {
  n: number
  id: number
  club: string
  topic: string
  text: string
  score: number | null
  cited: boolean
}

export interface Candidate {
  id: number
  club: string
  topic: string
  bm25_rank: number | null
  dense_rank: number | null
  rerank_rank: number | null
  selected: boolean
}

export interface Trace {
  original_query: string
  rewritten_query: string
  clubs: string[]
  sub_queries: string[]
  expansions: { from: string; to: string }[]
  candidates: Candidate[]
  stages: { name: StageName; ms: number }[]
  llm_calls: number
  llm_cache_hits: number
  cache_hit?: boolean
  tokens: { in: number; out: number; estimated?: boolean }
  cost_usd: number
  incidents: { stage: string; error: string }[]
}

export interface DonePayload {
  answer: string
  abstained: boolean
  citations: Citation[]
  retrieved_ids: number[]
  trace: Trace
  latency_ms: number
}

export type ServerEvent =
  | { event: 'stage'; data: StageEvent }
  | { event: 'token'; data: { text: string } }
  | { event: 'incident'; data: IncidentEvent }
  | { event: 'ping'; data: Record<string, never> }
  | { event: 'done'; data: DonePayload }
  | { event: 'error'; data: { message: string } }

export interface Suggestion {
  text: string
  tag: string
}
