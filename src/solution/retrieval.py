"""Truy xuất hybrid: BM25 (bỏ dấu) + dense bge-m3, gộp bằng Reciprocal Rank Fusion (RRF).

Mỗi nguồn tín hiệu tạo một danh sách xếp hạng; RRF cộng điểm 1 / (k + hạng) có trọng số.
RRF chỉ dùng thứ hạng nên không cần chuẩn hóa thang điểm giữa BM25 và cosine.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass

import numpy as np

from neorag.data import Document
from solution.bm25 import BM25
from solution.query import QueryPlan
from solution.textproc import expand_abbreviations, fold, tokens


@dataclass
class RetrievalConfig:
    use_bm25: bool = True
    use_dense: bool = True
    rrf_k: int = 60
    w_bm25: float = 1.0
    w_dense_rewritten: float = 1.0
    w_dense_original: float = 0.2  # câu gốc không dấu embed kém; bench: 0.5 -> 0.2 tăng ~1.8 điểm
    w_dense_sub: float = 0.7
    club_boost: float = 1.0  # cộng club_boost / rrf_k cho đoạn thuộc CLB được hỏi
    depth: int = 30  # số đoạn mỗi danh sách đưa vào RRF


def doc_repr(d: Document) -> str:
    """Văn bản đại diện của đoạn khi index: thêm CLB và chủ đề làm ngữ cảnh."""
    return f"{d.club} | {d.topic}\n{d.text}"


def rrf(rankings: list[tuple[list[int], float]], k: int) -> dict[int, float]:
    """rankings: [(danh sách index đã xếp hạng, trọng số)] -> {index: điểm RRF}."""
    scores: dict[int, float] = defaultdict(float)
    for ranking, weight in rankings:
        for rank, idx in enumerate(ranking, 1):
            scores[idx] += weight / (k + rank)
    return scores


class HybridRetriever:
    def __init__(self, embedder, config: RetrievalConfig | None = None):
        self.embedder = embedder
        self.config = config or RetrievalConfig()

    def index(self, corpus: list[Document]) -> None:
        self.docs = corpus
        texts = [doc_repr(d) for d in corpus]
        self.bm25 = BM25([tokens(t) for t in texts])
        self.doc_vectors = self.embedder.embed(texts) if self.config.use_dense else None

    def _top(self, scores: np.ndarray) -> list[int]:
        return [int(i) for i in np.argsort(-scores, kind="stable")[: self.config.depth]]

    def rankings(self, plan: QueryPlan) -> list[tuple[list[int], float]]:
        cfg = self.config
        out: list[tuple[list[int], float]] = []
        if cfg.use_bm25:
            bm25_query = " ".join(
                [expand_abbreviations(fold(plan.original)), plan.rewritten, *plan.sub_queries]
            )
            out.append((self._top(self.bm25.scores(tokens(bm25_query))), cfg.w_bm25))
        if cfg.use_dense:
            texts = [plan.rewritten]
            weights = [cfg.w_dense_rewritten]
            if fold(plan.original) != fold(plan.rewritten):
                texts.append(plan.original)
                weights.append(cfg.w_dense_original)
            texts += plan.sub_queries
            weights += [cfg.w_dense_sub] * len(plan.sub_queries)
            q_vectors = self.embedder.embed(texts)
            for vec, w in zip(q_vectors, weights, strict=True):
                out.append((self._top(self.doc_vectors @ vec), w))
        return out

    def retrieve(self, plan: QueryPlan, n: int = 10) -> list[Document]:
        cfg = self.config
        scores = rrf(self.rankings(plan), cfg.rrf_k)
        targets = plan.club_names
        # Chỉ ưu tiên khi câu hỏi nhắm tới một phần các CLB (hỏi chung cả 3 thì không lọc).
        if targets and cfg.club_boost and len(targets - {"Cộng đồng S2B"}) < 3:
            for idx in scores:
                if self.docs[idx].club in targets:
                    scores[idx] += cfg.club_boost / cfg.rrf_k
        ranked = sorted(scores, key=lambda i: (-scores[i], i))
        return [self.docs[i] for i in ranked[:n]]
