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
from solution.query import CLUBS, QueryPlan
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
    index_metadata: bool = True  # ghép "CLB | chủ đề" vào đầu đoạn khi index BM25 và dense
    use_rerank: bool = False  # rerank bằng cross-encoder local (solution.rerank)
    rerank_depth: int = 20  # số ứng viên từ RRF đưa vào cross-encoder
    w_rerank: float = 2.0  # trọng số danh sách xếp hạng của cross-encoder khi gộp RRF lần hai
    diversify_clubs: bool = True  # câu hỏi nhiều CLB: đảm bảo mỗi CLB có >= 1 đoạn trong top-5
    diversify_prefer_intro: bool = False  # đại diện của mỗi CLB là đoạn "Giới thiệu chung" nếu có
    # E6: Synthetic Question Anchors (solution.anchors, data/solution/doc_anchors.jsonl)
    use_anchors: bool = True  # bench E6: Retrieval 87.99 -> 91.21
    w_anchor_bm25: float = 1.5  # BM25 trên câu hỏi giả định + thực thể của mỗi đoạn
    # Dense trên anchors (max cosine với từng câu hỏi giả định): bench cho thấy làm giảm điểm -> tắt.
    w_anchor_dense: float = 0.0  # bản viết lại
    w_anchor_dense_original: float = 0.0  # câu gốc
    w_anchor_dense_sub: float = 0.0  # câu hỏi con


def doc_repr(d: Document, metadata: bool = True) -> str:
    """Văn bản đại diện của đoạn khi index: thêm CLB và chủ đề làm ngữ cảnh."""
    return f"{d.club} | {d.topic}\n{d.text}" if metadata else d.text


def rrf(rankings: list[tuple[list[int], float]], k: int) -> dict[int, float]:
    """rankings: [(danh sách index đã xếp hạng, trọng số)] -> {index: điểm RRF}."""
    scores: dict[int, float] = defaultdict(float)
    for ranking, weight in rankings:
        for rank, idx in enumerate(ranking, 1):
            scores[idx] += weight / (k + rank)
    return scores


class HybridRetriever:
    def __init__(self, embedder, config: RetrievalConfig | None = None, reranker=None):
        self.embedder = embedder
        self.config = config or RetrievalConfig()
        self.reranker = reranker  # CrossEncoderReranker, chỉ dùng khi config.use_rerank

    def index(self, corpus: list[Document]) -> None:
        self.docs = corpus
        texts = [doc_repr(d, self.config.index_metadata) for d in corpus]
        self.bm25 = BM25([tokens(t) for t in texts])
        self.doc_vectors = self.embedder.embed(texts) if self.config.use_dense else None
        self.anchor_bm25 = self.anchor_vectors = self.anchor_owner = None
        if self.config.use_anchors:
            self._index_anchors(corpus)

    def _index_anchors(self, corpus: list[Document]) -> None:
        from solution.anchors import load

        anchors = load()
        if not anchors:
            raise FileNotFoundError(
                "Chưa có data/solution/doc_anchors.jsonl: chạy python -m solution anchors"
            )
        per_doc = [anchors.get(d.id) for d in corpus]
        self.anchor_bm25 = BM25([tokens(a.text()) if a else [] for a in per_doc])
        questions, owner = [], []
        for i, a in enumerate(per_doc):
            for q in a.questions if a else []:
                questions.append(q)
                owner.append(i)
        self.anchor_vectors = self.embedder.embed(questions)
        self.anchor_owner = np.asarray(owner)

    def _anchor_doc_scores(self, vec: np.ndarray) -> np.ndarray:
        """Điểm của đoạn = max cosine giữa câu hỏi và các câu hỏi giả định của đoạn đó."""
        sims = self.anchor_vectors @ vec
        best = np.full(len(self.docs), -1.0, dtype=np.float32)
        np.maximum.at(best, self.anchor_owner, sims)
        return best

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
        if cfg.use_anchors and self.anchor_bm25 is not None:
            bm25_query = " ".join(
                [expand_abbreviations(fold(plan.original)), plan.rewritten, *plan.sub_queries]
            )
            out.append((self._top(self.anchor_bm25.scores(tokens(bm25_query))), cfg.w_anchor_bm25))
            texts = [plan.rewritten, plan.original, *plan.sub_queries]
            weights = [
                cfg.w_anchor_dense,
                cfg.w_anchor_dense_original,
                *[cfg.w_anchor_dense_sub] * len(plan.sub_queries),
            ]
            for vec, w in zip(self.embedder.embed(texts), weights, strict=True):
                if w:
                    out.append((self._top(self._anchor_doc_scores(vec)), w))
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
        if cfg.use_rerank and self.reranker is not None:
            ranked = self._rerank(plan, ranked, scores)
        if cfg.diversify_clubs:
            ranked = self._diversify(plan, ranked)
        return [self.docs[i] for i in ranked[:n]]

    def _rerank(self, plan: QueryPlan, ranked: list[int], scores: dict[int, float]) -> list[int]:
        """Gộp lần hai: thứ hạng RRF + thứ hạng cross-encoder (trọng số w_rerank) trên top-N."""
        cfg = self.config
        head = ranked[: cfg.rerank_depth]
        ce = self.reranker.score([plan.rewritten, *plan.sub_queries], [self.docs[i] for i in head])
        ce_ranking = sorted(head, key=lambda i: (-ce[self.docs[i].id], i))
        fused = rrf([(head, 1.0), (ce_ranking, cfg.w_rerank)], cfg.rrf_k)
        return sorted(head, key=lambda i: (-fused[i], i)) + ranked[cfg.rerank_depth :]

    def _diversify(self, plan: QueryPlan, ranked: list[int], k: int = 5) -> list[int]:
        """Câu hỏi về >= 2 CLB: mỗi CLB có một đoạn đại diện trong top-k.

        Đại diện = đoạn xếp hạng cao nhất của CLB đó, hoặc đoạn "Giới thiệu chung" của CLB nếu bật
        diversify_prefer_intro (câu so sánh thường cần thông tin tổng quan: ngày thành lập, lĩnh vực).
        Đoạn bị thay là đoạn thấp nhất trong top-k không phải đại diện, ưu tiên đoạn của CLB không được
        hỏi (vd. đoạn chung của S2B) rồi tới đoạn của CLB đang có nhiều hơn một đoạn.
        """
        clubs = [CLUBS[c] for c in plan.clubs if c != "s2b"]
        if len(clubs) < 2:
            return ranked
        prefer_intro = self.config.diversify_prefer_intro
        top, protected = ranked[:k], set()
        for club in clubs:
            members = [i for i in ranked if self.docs[i].club == club]
            if not members:
                continue
            rep = members[0]
            if prefer_intro:
                rep = next((i for i in members if self.docs[i].topic == "Giới thiệu chung"), rep)
            elif any(i in top for i in members):
                rep = next(i for i in top if i in members)
            if rep in top:
                protected.add(rep)
                continue
            counts = {c: sum(self.docs[i].club == c for i in top) for c in clubs}
            victim = next(
                (
                    i
                    for i in reversed(top)
                    if i not in protected
                    and (self.docs[i].club not in clubs or counts[self.docs[i].club] > 1)
                ),
                None,
            )
            if victim is None:
                continue
            top[top.index(victim)] = rep
            protected.add(rep)
        rest = [i for i in ranked if i not in top]
        return top + rest
