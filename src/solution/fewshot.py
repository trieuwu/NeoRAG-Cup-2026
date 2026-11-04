"""Dynamic Few-Shot: chọn các cặp (câu hỏi, đáp án chuẩn) của tập TRAIN giống câu hỏi hiện tại nhất.

Quy định cho phép dùng tập train để xây few-shot (docs/rules.md mục 1). Mục đích là dạy Haiku VĂN PHONG,
ĐỘ DÀI và CÁCH MỞ ĐẦU của đáp án chuẩn theo đúng dạng câu hỏi (so sánh, tư vấn, không có đáp án...).

Chống leakage (Leave-One-Out): luôn loại ví dụ có câu hỏi trùng với câu đang hỏi (so sánh sau khi bỏ dấu),
nên khi chấm trên chính tập train, câu hỏi không bao giờ thấy đáp án của chính nó.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from neorag.data import DATA_DIR, read_jsonl
from solution.bm25 import BM25
from solution.query import QueryPlan
from solution.retrieval import rrf
from solution.textproc import expand_abbreviations, fold, tokens

TRAIN_PATH = DATA_DIR / "train" / "questions.jsonl"


@dataclass(frozen=True)
class Example:
    id: str
    query: str
    answer: str
    answerable: bool


class FewShotSelector:
    def __init__(self, embedder, k: int = 4, path=TRAIN_PATH):
        self.embedder, self.k = embedder, k
        rows = read_jsonl(path)
        self.examples = [
            Example(r["id"], r["query"], r["answer"], bool(r.get("answerable", True)))
            for r in rows
            if r.get("answer")
        ]
        self._folded = [fold(e.query) for e in self.examples]
        self.bm25 = BM25([tokens(expand_abbreviations(f)) for f in self._folded])
        self.vectors = embedder.embed([e.query for e in self.examples])

    def select(self, plan: QueryPlan) -> list[Example]:
        banned = {fold(plan.original), fold(plan.rewritten)}  # Leave-One-Out
        query = " ".join([expand_abbreviations(fold(plan.original)), plan.rewritten])
        lexical = np.argsort(-self.bm25.scores(tokens(query)), kind="stable")[:30]
        dense = np.argsort(
            -(self.vectors @ self.embedder.embed([plan.rewritten])[0]), kind="stable"
        )[:30]
        scores = rrf([([int(i) for i in lexical], 1.0), ([int(i) for i in dense], 1.0)], k=60)
        ranked = sorted(scores, key=lambda i: (-scores[i], i))
        picked = [self.examples[i] for i in ranked if self._folded[i] not in banned][: self.k]
        # Thứ tự: ví dụ giống nhất đặt cuối, sát câu hỏi thật.
        return picked[::-1]
