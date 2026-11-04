"""Rerank bằng cross-encoder chạy local (mặc định BAAI/bge-reranker-v2-m3), không tốn ngân sách API.

Khác với embedding (mã hóa câu hỏi và đoạn văn riêng rẽ), cross-encoder đọc cặp (câu hỏi, đoạn văn)
cùng lúc nên chấm độ liên quan chính xác hơn, đổi lại chậm hơn: chỉ dùng cho top-N ứng viên từ RRF.

Điểm được cache trong SQLite (.cache/rerank.sqlite) theo (model, câu hỏi, id đoạn), nên chạy lại
bench hay pipeline trên cùng câu hỏi không phải tính lại. Cần: python scripts/install.py --local
"""

from __future__ import annotations

import hashlib
import json
import os
import sqlite3
import threading
from pathlib import Path

from neorag.data import Document

DEFAULT_MODEL = "BAAI/bge-reranker-v2-m3"


class _ScoreCache:
    def __init__(self, path: str | Path):
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(path), check_same_thread=False)
        self._conn.execute("CREATE TABLE IF NOT EXISTS s (k TEXT PRIMARY KEY, v REAL)")
        self._lock = threading.Lock()

    @staticmethod
    def key(*parts: object) -> str:
        return hashlib.sha256(json.dumps(parts, ensure_ascii=False).encode()).hexdigest()

    def get_many(self, keys: list[str]) -> dict[str, float]:
        with self._lock:
            out = {}
            for i in range(0, len(keys), 500):
                chunk = keys[i : i + 500]
                q = f"SELECT k, v FROM s WHERE k IN ({','.join('?' * len(chunk))})"
                out.update(dict(self._conn.execute(q, chunk).fetchall()))
            return out

    def set_many(self, items: dict[str, float]) -> None:
        with self._lock:
            self._conn.executemany("INSERT OR REPLACE INTO s VALUES (?, ?)", list(items.items()))
            self._conn.commit()


class CrossEncoderReranker:
    def __init__(
        self,
        model_name: str | None = None,
        cache_path: str | Path = ".cache/rerank.sqlite",
        batch_size: int = 16,
    ):
        self.model_name = model_name or os.getenv("RERANK_MODEL", DEFAULT_MODEL)
        self.cache = _ScoreCache(cache_path)
        self.batch_size = batch_size
        self._model = None
        self._lock = threading.Lock()

    def _load(self):
        with self._lock:
            if self._model is None:
                import torch
                from sentence_transformers import CrossEncoder

                device = "cuda" if torch.cuda.is_available() else "cpu"
                self._model = CrossEncoder(self.model_name, max_length=512, device=device)
                if device == "cuda":
                    self._model.model.half()  # fp16 trên GPU: nhanh gấp ~2 lần
        return self._model

    @property
    def device(self) -> str:
        return str(self._load().device)

    def score(self, queries: list[str], docs: list[Document]) -> dict[int, float]:
        """Điểm của mỗi đoạn = max điểm cross-encoder trên các câu hỏi (bản viết lại + câu hỏi con)."""
        pairs = [(q, d) for q in queries for d in docs]
        keys = [self.cache.key(self.model_name, q, d.id, d.text) for q, d in pairs]
        cached = self.cache.get_many(keys)
        todo = [(k, q, d) for k, (q, d) in zip(keys, pairs, strict=True) if k not in cached]
        if todo:
            model = self._load()
            with self._lock:  # một model dùng chung giữa các luồng
                values = model.predict(
                    [(q, f"{d.club} | {d.topic}\n{d.text}") for _, q, d in todo],
                    batch_size=self.batch_size,
                    show_progress_bar=False,
                )
            fresh = {k: float(v) for (k, _, _), v in zip(todo, values, strict=True)}
            self.cache.set_many(fresh)
            cached.update(fresh)
        best: dict[int, float] = {}
        for k, (_, d) in zip(keys, pairs, strict=True):
            best[d.id] = max(best.get(d.id, float("-inf")), cached[k])
        return best


LLM_RERANK_SYSTEM = """Bạn xếp hạng tài liệu cho hệ thống hỏi đáp về cộng đồng S2B tại PTIT (CLB Lập Trình PTIT, CLB Multimedia PTIT, CLB Nhà Sáng Tạo Game PTIT).
Cho một câu hỏi và các đoạn tài liệu có mã [id]. Chọn các đoạn chứa thông tin giúp trả lời câu hỏi và xếp
đoạn liên quan nhất lên đầu. Đoạn phải đúng CLB, đúng đối tượng và đúng mốc thời gian được hỏi. Câu hỏi nhiều ý
hoặc so sánh thì chọn đoạn cho TỪNG ý. Bỏ các đoạn không liên quan.
Chỉ trả về JSON: {"ranking": [id, id, ...]} (tối đa 8 id), không giải thích."""


class LLMReranker:
    """Rerank listwise bằng claude-haiku-5-5 qua gateway (cùng interface score() với CrossEncoderReranker).

    Một lời gọi mỗi câu hỏi, cache bởi LLMClient. Điểm của đoạn = (số đoạn - vị trí) nếu được chọn, -1 nếu
    không được chọn; pipeline gộp thứ hạng này với RRF như cross-encoder.
    """

    def __init__(self, llm, model: str):
        self.llm, self.model = llm, model

    def score(self, queries: list[str], docs: list[Document]) -> dict[int, float]:
        question = queries[0] + (
            "\nCác ý cần tìm: " + " | ".join(queries[1:]) if len(queries) > 1 else ""
        )
        context = "\n\n".join(f"[{d.id}] ({d.club} | {d.topic})\n{d.text}" for d in docs)
        reply = self.llm.chat(
            [
                {"role": "system", "content": LLM_RERANK_SYSTEM},
                {"role": "user", "content": f"CÂU HỎI: {question}\n\nTÀI LIỆU:\n{context}"},
            ],
            model=self.model,
        )
        start, end = reply.find("{"), reply.rfind("}")
        try:
            ranking = json.loads(reply[start : end + 1]).get("ranking", []) if start >= 0 else []
        except (json.JSONDecodeError, AttributeError):
            ranking = []
        valid = {d.id for d in docs}
        order = [
            int(i)
            for i in ranking
            if isinstance(i, int | str) and str(i).isdigit() and int(i) in valid
        ]
        order = list(dict.fromkeys(order))
        scores = {d.id: -1.0 for d in docs}
        for pos, doc_id in enumerate(order):
            scores[doc_id] = float(len(docs) - pos)
        return scores
