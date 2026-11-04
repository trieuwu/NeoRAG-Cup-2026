"""SolutionPipeline: QueryRewriter -> HybridRetriever -> Generator.

Chạy:  neorag run train --no-judge --pipeline solution.pipeline:SolutionPipeline

Mọi tham số chỉnh được qua biến môi trường RAG_* (để chạy ablation không cần sửa code), ví dụ:
    RAG_REWRITE=0          tắt bước viết lại câu hỏi
    RAG_USE_BM25=0         chỉ dùng dense
    RAG_CLUB_BOOST=0       tắt ưu tiên theo CLB
    RAG_PROMPT=baseline    dùng prompt của baseline
    RAG_CONTEXT_K=5        số đoạn đưa vào prompt
    RAG_USE_RERANK=1       rerank bằng cross-encoder local (cần install.py --local)
    RAG_DIVERSIFY_CLUBS=1  câu hỏi nhiều CLB: mỗi CLB có >= 1 đoạn trong top-5
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field, fields

from neorag.data import Document
from neorag.llm import LLMClient
from neorag.pipelines.base import RAGOutput, RAGPipeline
from neorag.pipelines.baseline import GatewayEmbedder
from solution.prompts import answer_messages
from solution.query import QueryPlan, QueryRewriter
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
    prompt: str = (
        "v5"  # "v5" (v4 + bỏ câu phụ, dùng tên gọi của người hỏi) | "v4" | "v3" | "v2" | "baseline"
    )
    context_k: int = 5  # số đoạn đưa vào prompt sinh câu trả lời
    n_retrieved: int = 10  # số id nộp để chấm retrieval
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


class SolutionPipeline(RAGPipeline):
    def __init__(self, config: PipelineConfig | None = None, llm: LLMClient | None = None):
        self.config = config or PipelineConfig.from_env()
        self.llm_model = os.getenv("LLM_MODEL", "claude-haiku-5-5")
        self.llm = llm or LLMClient(cache_path=".cache/solution.sqlite")
        self.embedder = GatewayEmbedder(self.llm, os.getenv("EMBEDDING_MODEL", "bge-m3"))
        self.rewriter = QueryRewriter(self.llm, self.llm_model, self.config.rewrite_prompt)
        reranker = None
        if self.config.retrieval.use_rerank:
            from solution.rerank import CrossEncoderReranker

            reranker = CrossEncoderReranker()
        self.retriever = HybridRetriever(self.embedder, self.config.retrieval, reranker)
        self.last_trace: Trace | None = None

    def index(self, corpus: list[Document]) -> None:
        self.retriever.index(corpus)

    def plan(self, query: str) -> QueryPlan:
        return self.rewriter(query) if self.config.rewrite else QueryPlan(query, query)

    def retrieve(self, query: str) -> tuple[QueryPlan, list[Document]]:
        plan = self.plan(query)
        return plan, self.retriever.retrieve(plan, self.config.n_retrieved)

    def run(self, query: str) -> RAGOutput:
        plan, docs = self.retrieve(query)
        messages = answer_messages(
            query, plan.rewritten, docs[: self.config.context_k], self.config.prompt
        )
        answer = self.llm.chat(messages, model=self.llm_model)
        self.last_trace = Trace(plan, docs)
        return RAGOutput(answer=answer, retrieved_ids=[d.id for d in docs])
