"""Chạy pipeline từng bước cho chatbot: phát sự kiện theo giai đoạn, stream câu trả lời, kèm trace đầy đủ.

Dùng cho `app/api.py` (SSE) và giao diện demo. KHÔNG dùng khi tạo bài nộp: `SolutionPipeline.run` (bài nộp)
không đi qua module này, nên chế độ trích dẫn `[n]` và streaming không ảnh hưởng output chấm điểm.

Các bước giống hệt `SolutionPipeline`: viết lại câu hỏi → BM25 + dense gộp RRF → rerank Haiku → đa dạng hóa CLB
→ sinh câu trả lời. Mọi lời gọi LLM vẫn qua cache của LLMClient (câu đã hỏi trả lời tức thì, không tốn tiền).
"""

from __future__ import annotations

import math
import re
import threading
import time
from collections.abc import Callable, Iterator
from dataclasses import dataclass, field

from neorag.llm import _key as cache_key
from solution import resilience
from solution.pipeline import SolutionPipeline
from solution.prompts import answer_messages
from solution.resilience import (
    LLMUnavailable,
    clip_answer,
    collect_incidents,
    fallback_answer,
    record,
    start_incidents,
)
from solution.retrieval import rrf
from solution.textproc import ABBREVIATIONS, PHRASE_ABBREVIATIONS, fold

PRICE_IN, PRICE_OUT = 0.10 / 1e6, 0.50 / 1e6  # USD/token, giá niêm yết claude-haiku-5-5
CITE_RULE = (
    "\n\nCHẾ ĐỘ TRÍCH DẪN (chatbot): cuối mỗi câu, ghi số thứ tự của đoạn TÀI LIỆU đã dùng trong ngoặc vuông, "
    "ví dụ [1] hoặc [1][3]. Câu từ chối không cần trích dẫn."
)
_CITATION = re.compile(r"\[(\d+)\]")
_FIRST_SENTENCE = re.compile(r"^.*?(?:[.!?…](?=\s|$)|$)", re.S)
_REFUSAL = ("không có thông tin", "không đề cập", "không có dữ liệu")

EventSink = Callable[[str, dict], None]


def is_refusal(answer: str) -> bool:
    """Câu trả lời là câu TỪ CHỐI: câu đầu tiên nói tài liệu không có thông tin VÀ không có trích dẫn [n]
    nào. Câu trả lời một phần (câu đầu trả lời, câu sau nói thiếu dữ liệu, hoặc có trích dẫn) → False."""
    text = (answer or "").strip()
    if _CITATION.search(text):
        return False
    first = _FIRST_SENTENCE.match(text).group().lower()
    return any(p in first for p in _REFUSAL)


def _tokens(text: str) -> int:
    """Ước lượng số token (tiếng Việt ~3.5 ký tự/token) cho lời gọi không có usage trả về."""
    return max(1, round(len(text) / 3.5))


@dataclass
class CallMeter:
    """Đếm lời gọi LLM của một yêu cầu chatbot: lời gọi trúng cache không tốn tiền."""

    calls: int = 0
    cached: int = 0
    tokens_in: int = 0
    tokens_out: int = 0

    def add(self, messages: list[dict], reply: str, cached: bool) -> None:
        self.calls += 1
        if cached:
            self.cached += 1
            return
        self.tokens_in += _tokens("".join(m["content"] for m in messages))
        self.tokens_out += _tokens(reply)

    @property
    def cost_usd(self) -> float:
        return round(self.tokens_in * PRICE_IN + self.tokens_out * PRICE_OUT, 6)


class _MeteredClient:
    """Bọc LLMClient: ghi lời gọi chat vào CallMeter của luồng hiện tại (mỗi request API một luồng)."""

    def __init__(self, inner):
        self.inner = inner
        self.local = threading.local()

    def __getattr__(self, name):
        return getattr(self.inner, name)

    def is_cached(self, messages: list[dict], model: str) -> bool:
        cache = getattr(self.inner, "_cache", None)
        endpoint = getattr(self.inner, "_endpoint", "")
        return (
            bool(cache)
            and cache.get(cache_key("chat", endpoint, model, None, messages)) is not None
        )

    def chat(self, messages, model, **kwargs):
        cached = self.is_cached(messages, model)
        reply = self.inner.chat(messages, model=model, **kwargs)
        meter = getattr(self.local, "meter", None)
        if meter is not None:
            meter.add(messages, reply, cached)
        return reply


@dataclass
class StageTimer:
    stages: list[dict] = field(default_factory=list)

    def run(self, name: str, fn):
        start = time.perf_counter()
        result = fn()
        self.stages.append({"name": name, "ms": round((time.perf_counter() - start) * 1000, 1)})
        return result


def expansions(query: str) -> list[dict]:
    """Viết tắt trong câu hỏi được BM25 mở rộng (solution.textproc), để hiển thị cho người dùng."""
    folded = fold(query)
    padded = f" {folded} "
    out = [
        {"from": p, "to": full} for p, full in PHRASE_ABBREVIATIONS.items() if f" {p} " in padded
    ]
    seen = set()
    for w in folded.split():
        if w in ABBREVIATIONS and w not in seen:
            seen.add(w)
            out.append({"from": w, "to": ABBREVIATIONS[w]})
    return out


class TracedChat:
    """Bọc một SolutionPipeline đã index. `stream(query)` sinh (loại sự kiện, dữ liệu)."""

    def __init__(self, pipeline: SolutionPipeline):
        self.pipe = pipeline
        llm = pipeline.llm  # ResilientLLM -> LLMClient
        if not isinstance(llm.inner, _MeteredClient):
            llm.inner = _MeteredClient(llm.inner)
        self.client: _MeteredClient = llm.inner
        self._local = (
            threading.local()
        )  # giai đoạn hiện tại + nơi nhận sự kiện của request (theo luồng)
        self._sleep = llm.sleep
        llm.sleep = self._retry_sleep  # ResilientLLM gọi sleep(wait) trước mỗi lần thử lại

    # ------------------------------------------------------------ sự cố

    def _emit(self, kind: str, data: dict) -> None:
        sink = getattr(self._local, "sink", None)
        if sink is not None:
            sink(kind, data)

    def _retry_sleep(self, wait_s: float) -> None:
        backoff = getattr(self.pipe.llm, "backoff", 0) or 0
        attempt = 1 + round(math.log(wait_s / backoff, 3)) if backoff and wait_s > 0 else None
        stage = getattr(self._local, "stage", None)
        self._emit(
            "incident", {"type": "retry", "stage": stage, "attempt": attempt, "wait_s": wait_s}
        )
        self._sleep(wait_s)

    def _report_fallbacks(self) -> None:
        """Phát sự kiện cho các sự cố mới trong sổ của resilience (bước đã chuyển sang dự phòng)."""
        items = getattr(resilience._local, "items", [])
        seen = getattr(self._local, "seen", 0)
        for item in items[seen:]:
            self._emit(
                "incident",
                {
                    "type": "fallback",
                    "stage": item["stage"],
                    "attempt": None,
                    "wait_s": None,
                    "error": item["error"],
                },
            )
        self._local.seen = len(items)

    # ------------------------------------------------------------ các bước

    def _candidates(self, plan, lists, head, rerank_order, docs) -> list[dict]:
        cfg = self.pipe.config.retrieval
        bm25 = lists[0][0] if cfg.use_bm25 and lists else []
        dense_at = 1 if cfg.use_bm25 else 0
        dense = lists[dense_at][0] if cfg.use_dense and len(lists) > dense_at else []
        selected = {d.id for d in docs[: self.pipe.config.context_k]}

        def rank_of(seq, i):
            return seq.index(i) + 1 if i in seq else None

        docs_all = self.pipe.retriever.docs
        return [
            {
                "id": docs_all[i].id,
                "club": docs_all[i].club,
                "topic": docs_all[i].topic,
                "bm25_rank": rank_of(
                    bm25, i
                ),  # hạng trong danh sách BM25 (top-30), null nếu không có
                "dense_rank": rank_of(dense, i),  # hạng dense theo bản viết lại
                "rerank_rank": rank_of(rerank_order, i),  # thứ tự Haiku chọn, null nếu không chọn
                "selected": docs_all[i].id in selected,  # nằm trong top-5 đưa vào prompt
            }
            for i in head
        ]

    def _rerank(self, plan, ranked, head):
        """Như HybridRetriever._rerank nhưng giữ lại thứ hạng của reranker để hiển thị."""
        retr, cfg = self.pipe.retriever, self.pipe.config.retrieval
        try:
            scores = retr.reranker.score(
                [plan.rewritten, *plan.sub_queries], [retr.docs[i] for i in head]
            )
        except Exception as exc:  # noqa: BLE001 - như pipeline: giữ thứ hạng local
            record("rerank", exc)
            return ranked, [], rrf([(ranked, 1.0)], cfg.rrf_k)
        order = sorted(
            (i for i in head if retr.docs[i].id in scores),
            key=lambda i: (-scores[retr.docs[i].id], i),
        )
        fused = rrf([(head, 1.0), (order, cfg.w_rerank)], cfg.rrf_k)
        pool = set(head)
        new_ranked = sorted(head, key=lambda i: (-fused[i], i)) + [
            i for i in ranked if i not in pool
        ]
        return new_ranked, order, fused

    def _generate(self, query, plan, docs, cite: bool) -> Iterator[str]:
        messages = answer_messages(
            query, plan.rewritten, docs[: self.pipe.config.context_k], self.pipe.config.prompt, None
        )
        if cite:
            messages[0] = {**messages[0], "content": messages[0]["content"] + CITE_RULE}
        model = self.pipe.llm_model
        inner = self.client.inner
        meter = self.client.local.meter
        cache = getattr(inner, "_cache", None)
        key = cache_key("chat", getattr(inner, "_endpoint", ""), model, None, messages)
        if cache and (hit := cache.get(key)) is not None:
            meter.add(messages, hit, cached=True)
            yield from re.findall(r"\S+\s*", hit)  # trả từng từ để giao diện hiển thị đều
            return
        parts: list[str] = []
        try:
            stream = inner._client.chat.completions.create(
                model=model, messages=messages, stream=True
            )
            for chunk in stream:
                delta = chunk.choices[0].delta.content if chunk.choices else None
                if delta:
                    parts.append(delta)
                    yield delta
            text = "".join(parts).strip()
            if text and cache:
                cache.set(key, text)
            meter.add(messages, text, cached=False)
        except Exception as exc:  # noqa: BLE001 - stream lỗi: thử một lời gọi thường (có retry)
            if parts:
                record("generate_stream", exc)
                return
            try:
                text = self.pipe.llm.chat(messages, model=model)
            except LLMUnavailable as exc2:
                record("generate", exc2)
                text = fallback_answer(docs)
            yield text

    # ------------------------------------------------------------ API

    def stream(
        self,
        query: str,
        cite: bool = True,
        on_event: EventSink | None = None,
        cancel: threading.Event | None = None,
    ) -> Iterator[tuple[str, dict]]:
        """Sinh các sự kiện ("stage" | "token" | "done", dữ liệu). Phải được lặp hết trên CÙNG một luồng.

        on_event: nhận sự kiện phát giữa chừng một bước ("incident": thử lại, dự phòng) ngay khi xảy ra.
        cancel: được đặt khi client ngắt kết nối; kiểm tra giữa các bước, dừng mà không phát "done".
        """
        started = time.perf_counter()
        start_incidents()
        meter = CallMeter()
        self.client.local.meter = meter
        self._local.sink, self._local.seen = on_event, 0
        timer = StageTimer()
        retr, cfg = self.pipe.retriever, self.pipe.config.retrieval

        def begin(name):
            self._local.stage = name
            return ("stage", {"name": name, "status": "start"})

        def end(name):
            self._report_fallbacks()
            return ("stage", {"name": name, "status": "done", "ms": timer.stages[-1]["ms"]})

        def cancelled() -> bool:
            return cancel is not None and cancel.is_set()

        try:
            yield begin("rewrite")
            plan = timer.run("rewrite", lambda: self.pipe.plan(query))
            yield end("rewrite")
            if cancelled():
                return

            yield begin("retrieve")
            lists = timer.run("retrieve", lambda: retr.rankings(plan))
            ranked = retr.fused_ranking(plan)  # embedding vừa tính đã nằm trong cache
            yield end("retrieve")
            if cancelled():
                return

            head = retr.candidate_pool(plan, ranked)
            order, fused = [], rrf([(ranked, 1.0)], cfg.rrf_k)
            if cfg.use_rerank and retr.reranker is not None:
                yield begin("rerank")
                ranked, order, fused = timer.run("rerank", lambda: self._rerank(plan, ranked, head))
                yield end("rerank")
                if cancelled():
                    return
            if cfg.diversify_clubs:
                ranked = retr._diversify(plan, ranked)
            docs = [retr.docs[i] for i in ranked[: self.pipe.config.n_retrieved]]

            yield begin("generate")
            t0 = time.perf_counter()
            parts = []
            for token in self._generate(query, plan, docs, cite):
                if cancelled():
                    return  # client đã ngắt: bỏ phần còn lại (câu trả lời dở không được cache)
                parts.append(token)
                yield ("token", {"text": token})
            timer.stages.append(
                {"name": "generate", "ms": round((time.perf_counter() - t0) * 1000, 1)}
            )
            yield end("generate")
            answer = clip_answer("".join(parts)) or fallback_answer(docs)
        finally:
            self.client.local.meter = None
            self._local.sink = self._local.stage = None

        scores = {retr.docs[i].id: round(s * cfg.rrf_k, 4) for i, s in fused.items()}
        used = {int(n) for n in _CITATION.findall(answer)}
        citations = [
            {
                "n": n,
                "id": d.id,
                "club": d.club,
                "topic": d.topic,
                "text": d.text,
                "score": scores.get(d.id),
                "cited": n in used,
            }
            for n, d in enumerate(docs[: self.pipe.config.context_k], 1)
        ]
        yield (
            "done",
            {
                "answer": answer,
                "abstained": is_refusal(answer),
                "citations": citations,
                "retrieved_ids": [d.id for d in docs],
                "trace": {
                    "original_query": query,
                    "rewritten_query": plan.rewritten,
                    "clubs": plan.clubs,
                    "sub_queries": plan.sub_queries,
                    "expansions": expansions(query),
                    "candidates": self._candidates(plan, lists, head, order, docs),
                    "stages": timer.stages,
                    "llm_calls": meter.calls,
                    "llm_cache_hits": meter.cached,
                    "cache_hit": meter.calls > 0 and meter.cached == meter.calls,
                    "tokens": {"in": meter.tokens_in, "out": meter.tokens_out, "estimated": True},
                    "cost_usd": meter.cost_usd,
                    "incidents": collect_incidents(),
                },
                "latency_ms": round((time.perf_counter() - started) * 1000, 1),
            },
        )
