"""SolutionPipeline: QueryRewriter -> HybridRetriever -> Generator.

Chạy:  neorag run train --no-judge --pipeline solution.pipeline:SolutionPipeline

Mọi tham số chỉnh được qua biến môi trường RAG_* (để chạy ablation không cần sửa code), ví dụ:
    RAG_REWRITE=0          tắt bước viết lại câu hỏi
    RAG_USE_BM25=0         chỉ dùng dense
    RAG_CLUB_BOOST=0       tắt ưu tiên theo CLB
    RAG_PROMPT=baseline    dùng prompt của baseline
    RAG_CONTEXT_K=5        số đoạn đưa vào prompt
    RAG_USE_RERANK=1       rerank top-N (RAG_RERANK_BACKEND=llm: Haiku listwise; cross_encoder: local)
    RAG_RERANK_DEPTH=20    số ứng viên RRF đưa vào reranker
    RAG_RERANK_MAX=8       số đoạn tối đa reranker LLM được chọn
    RAG_ANCHORS_CANDIDATES_ONLY=1  (kèm RAG_USE_ANCHORS=1) anchors chỉ bổ sung ứng viên cho reranker
    RAG_DIVERSIFY_CLUBS=1  câu hỏi nhiều CLB: mỗi CLB có >= 1 đoạn trong top-5
    RAG_USE_ANCHORS=0      tắt Synthetic Question Anchors
    RAG_DYNAMIC_FEW_SHOT=1 ví dụ few-shot động từ train (Leave-One-Out)
    RAG_LOG_PATH=outputs/x_log.jsonl  ghi log từng câu (sự cố, fallback, độ dài, latency)
    RAG_CACHE_PATH=.cache/solution.sqlite  cache LLM; trỏ sang file mới = một lần chạy độc lập

Chống lỗi (solution.resilience): mọi lời gọi gateway được thử lại khi lỗi tạm thời; bước nào hỏng hẳn
thì dùng phương án dự phòng (câu hỏi gốc, thứ hạng local, trích đoạn đứng đầu), nên `run()` không bao giờ
ném exception và output luôn hợp lệ.
"""

from __future__ import annotations

import contextlib
import os
import time
from dataclasses import dataclass, field, fields

from neorag.data import Document
from neorag.llm import LLMClient
from neorag.pipelines.base import RAGOutput, RAGPipeline
from neorag.pipelines.baseline import GatewayEmbedder
from solution.prompts import answer_messages
from solution.query import QueryPlan, QueryRewriter
from solution.resilience import (
    LLMUnavailable,
    ResilientLLM,
    append_log,
    clip_answer,
    collect_incidents,
    fallback_answer,
    is_abstention,
    record,
    sanitize_ids,
    start_incidents,
)
from solution.retrieval import HybridRetriever, RetrievalConfig


def _coerce(value: str, current):
    if isinstance(current, bool):
        return value.strip().lower() in {"1", "true", "yes", "on"}
    return type(current)(value)


def _apply_env(obj) -> None:
    for f in fields(obj):
        raw = os.getenv(f"RAG_{f.name.upper()}")
        if raw is not None and not hasattr(getattr(obj, f.name), "__dataclass_fields__"):
            setattr(obj, f.name, _coerce(raw, getattr(obj, f.name)))


@dataclass
class PipelineConfig:
    rewrite: bool = True
    rewrite_prompt: str = "v3"  # "v3" (từ điển PTIT, phân giải chữ không dấu) | "v2" | "v1"
    # "v6" (câu đầu đủ chủ thể + khía cạnh, ví dụ động) | "v5" | "v4" | "v3" | "v2" | "baseline"
    prompt: str = "v5"  # E6 (v6 + few-shot động) thấp hơn trên Public -> giữ v5
    context_k: int = 5  # số đoạn đưa vào prompt sinh câu trả lời
    dynamic_few_shot: bool = False  # E6: Public SP -3.8 -> tắt mặc định
    few_shot_k: int = 4
    few_shot_style_only: bool = True  # bỏ ví dụ có đoạn đúng trùng các đoạn trong prompt
    n_retrieved: int = 10  # số id nộp để chấm retrieval
    log_path: str = ""  # RAG_LOG_PATH: file jsonl ghi log từng câu (rỗng = không ghi)
    cache_path: str = (
        ".cache/solution.sqlite"  # RAG_CACHE_PATH: cache của mọi lời gọi LLM/embedding
    )
    retrieval: RetrievalConfig = field(default_factory=RetrievalConfig)

    @classmethod
    def from_env(cls) -> PipelineConfig:
        cfg = cls()
        _apply_env(cfg)
        _apply_env(cfg.retrieval)
        return cfg


@dataclass
class Trace:
    """Thông tin trung gian của lần chạy gần nhất, dùng cho chatbot và phân tích lỗi."""

    plan: QueryPlan
    docs: list[Document]
    incidents: list[dict] = field(default_factory=list)


class SolutionPipeline(RAGPipeline):
    def __init__(self, config: PipelineConfig | None = None, llm: LLMClient | None = None):
        self.config = config or PipelineConfig.from_env()
        self.llm_model = os.getenv("LLM_MODEL", "claude-haiku-5-5")
        base = llm or LLMClient(cache_path=self.config.cache_path)
        self.llm = base if isinstance(base, ResilientLLM) else ResilientLLM(base)
        self.embedder = GatewayEmbedder(self.llm, os.getenv("EMBEDDING_MODEL", "bge-m3"))
        self.rewriter = QueryRewriter(self.llm, self.llm_model, self.config.rewrite_prompt)
        reranker = None
        if self.config.retrieval.use_rerank:
            if self.config.retrieval.rerank_backend == "llm":
                from solution.rerank import LLMReranker

                reranker = LLMReranker(
                    self.llm, self.llm_model, max_ids=self.config.retrieval.rerank_max
                )
            else:
                from solution.rerank import CrossEncoderReranker

                reranker = CrossEncoderReranker()
        self.retriever = HybridRetriever(self.embedder, self.config.retrieval, reranker)
        self.few_shot = None
        if self.config.dynamic_few_shot:
            from solution.fewshot import FewShotSelector

            self.few_shot = FewShotSelector(self.embedder, k=self.config.few_shot_k)
        self.last_trace: Trace | None = None

    def index(self, corpus: list[Document]) -> None:
        self.retriever.index(corpus)
        self._valid_ids = {d.id for d in corpus}

    def plan(self, query: str) -> QueryPlan:
        if not self.config.rewrite:
            return QueryPlan(query, query)
        try:
            return self.rewriter(query)
        except Exception as exc:  # noqa: BLE001 - viết lại câu hỏi lỗi: dùng câu hỏi gốc
            record("rewrite", exc)
            return QueryPlan(query, query)

    def retrieve(self, query: str) -> tuple[QueryPlan, list[Document]]:
        plan = self.plan(query)
        return plan, self.retriever.retrieve(plan, self.config.n_retrieved)

    def _examples(self, plan: QueryPlan, docs: list[Document]):
        if not self.few_shot:
            return None
        style_only = self.config.few_shot_style_only
        try:
            chosen = self.few_shot.select(
                plan, {d.id for d in docs[: self.config.context_k]} if style_only else None
            )
        except Exception as exc:  # noqa: BLE001 - không chọn được ví dụ: chạy không few-shot
            record("few_shot", exc)
            return None
        return [(e.query, e.answer) for e in chosen]

    def _answer(self, query: str, plan: QueryPlan, docs: list[Document]) -> str:
        messages = answer_messages(
            query,
            plan.rewritten,
            docs[: self.config.context_k],
            self.config.prompt,
            self._examples(plan, docs),
        )
        try:
            answer = self.llm.chat(messages, model=self.llm_model)
        except LLMUnavailable as exc:
            record("generate", exc)
            answer = ""
        if not answer.strip():
            record("generate", "không sinh được câu trả lời: trích đoạn đứng đầu")
            return fallback_answer(docs)
        return answer

    def run(self, query: str) -> RAGOutput:
        """Không bao giờ ném exception: lỗi ở bước nào thì bước đó dùng phương án dự phòng."""
        start_incidents()
        started = time.perf_counter()
        plan, docs = QueryPlan(query, query), []
        try:
            plan, docs = self.retrieve(query)
            answer = self._answer(query, plan, docs)
        except Exception as exc:  # noqa: BLE001 - lưới an toàn cuối cùng
            record("pipeline", exc)
            answer = ""
        ids = sanitize_ids([d.id for d in docs], self._valid_ids, self.config.n_retrieved)
        if not ids:
            record("retrieve", "không có id hợp lệ: dùng BM25 trên câu hỏi gốc")
            docs = self._local_docs(query)
            ids = sanitize_ids([d.id for d in docs], self._valid_ids, self.config.n_retrieved)
        answer = clip_answer(answer) or fallback_answer(docs)
        incidents = collect_incidents()
        self.last_trace = Trace(plan, docs, incidents)
        if self.config.log_path:
            self._log(query, plan, answer, ids, incidents, started)
        return RAGOutput(answer=answer, retrieved_ids=ids)

    def _local_docs(self, query: str) -> list[Document]:
        try:
            return self.retriever.local_ranking(query, self.config.n_retrieved)
        except Exception as exc:  # noqa: BLE001
            record("local_ranking", exc)
            return list(self.retriever.docs[: self.config.n_retrieved])

    def _log(self, query, plan, answer, ids, incidents, started) -> None:
        with contextlib.suppress(OSError):  # không ghi được log thì vẫn trả kết quả
            append_log(
                self.config.log_path,
                {
                    "query": query,
                    "rewritten": plan.rewritten,
                    "fallback_used": bool(incidents),
                    "incidents": incidents,
                    "abstained": is_abstention(answer),
                    "answer_chars": len(answer),
                    "n_ids": len(ids),
                    "latency_ms": round((time.perf_counter() - started) * 1000, 1),
                },
            )
