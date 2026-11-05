"""Mô phỏng lỗi gateway (không gọi mạng): pipeline không bao giờ ném exception, output luôn hợp lệ."""

from __future__ import annotations

import json
import threading
import time
from types import SimpleNamespace

import numpy as np
import pytest

from conftest import FakeEmbedder, FakeLLM
from neorag.llm import LLMClient
from solution.pipeline import PipelineConfig, SolutionPipeline
from solution.resilience import (
    LLMUnavailable,
    ResilientLLM,
    clip_answer,
    fallback_answer,
    is_transient,
    sanitize_ids,
)


class StatusError(Exception):
    def __init__(self, status_code: int):
        super().__init__(f"HTTP {status_code}")
        self.status_code = status_code


class APITimeoutError(Exception):  # cùng tên lớp với openai.APITimeoutError
    pass


def _responder(messages):
    system = messages[0]["content"]
    if "chuẩn hóa câu hỏi" in system:
        return json.dumps(
            {"query": "CLB Multimedia PTIT thành lập khi nào?", "clubs": ["multimedia"]}
        )
    if "xếp hạng tài liệu" in system:
        return json.dumps({"ranking": [2, 1]})
    return "CLB Multimedia PTIT thành lập ngày 10/11/2012."


def _pipeline(corpus, llm, **cfg):
    pipe = SolutionPipeline(PipelineConfig(**cfg), llm=llm)
    pipe.llm.sleep = lambda s: None  # không chờ backoff thật trong test
    pipe.retriever.embedder = FakeEmbedder()
    pipe.index(corpus)
    return pipe


def _failing(stage_text: str, exc: Exception, base=_responder):
    """LLM giả: lời gọi có system prompt chứa `stage_text` luôn lỗi, các lời gọi khác bình thường."""

    def responder(messages):
        if stage_text in messages[0]["content"]:
            raise exc
        return base(messages)

    return FakeLLM(responder)


def _assert_valid(out, corpus):
    assert 1 <= len(out.answer) <= 2000 and out.answer.strip()
    assert 1 <= len(out.retrieved_ids) <= 10
    assert len(set(out.retrieved_ids)) == len(out.retrieved_ids)
    assert set(out.retrieved_ids) <= {d.id for d in corpus}


# [1] Rewrite


@pytest.mark.parametrize(
    "reply", ["không phải JSON", '{"clubs": ["gcc"]}', '{"query": 5}', "[1, 2]"]
)
def test_rewrite_bad_json_uses_original_question(corpus, reply):
    def responder(messages):
        return reply if "chuẩn hóa câu hỏi" in messages[0]["content"] else _responder(messages)

    pipe = _pipeline(corpus, FakeLLM(responder))
    out = pipe.run("clb mm thanh lap khi nao")
    assert pipe.last_trace.plan.rewritten == "clb mm thanh lap khi nao"
    assert [i["stage"] for i in pipe.last_trace.incidents] == ["rewrite"]
    _assert_valid(out, corpus)


def test_rewrite_exception_uses_original_question(corpus):
    pipe = _pipeline(corpus, _failing("chuẩn hóa câu hỏi", StatusError(500)))
    out = pipe.run("clb mm thanh lap khi nao")
    assert pipe.last_trace.plan.rewritten == "clb mm thanh lap khi nao"
    assert "rewrite" in {i["stage"] for i in pipe.last_trace.incidents}
    _assert_valid(out, corpus)


# [2] Rerank


@pytest.mark.parametrize(
    "fault", ["JSON hỏng {{", '{"ranking": [999, "x"]}', StatusError(503), ValueError("lạ")]
)
def test_rerank_failure_falls_back_to_local_ranking(corpus, fault):
    def responder(messages):
        if "xếp hạng tài liệu" in messages[0]["content"]:
            if isinstance(fault, Exception):
                raise fault
            return fault
        return _responder(messages)

    pipe = _pipeline(corpus, FakeLLM(responder))
    out = pipe.run("clb mm thanh lap khi nao")
    local = _pipeline(corpus, FakeLLM(_responder))
    local.config.retrieval.use_rerank = False
    assert out.retrieved_ids == local.run("clb mm thanh lap khi nao").retrieved_ids
    assert "rerank" in {i["stage"] for i in pipe.last_trace.incidents}


def test_rerank_duplicate_ids_are_deduplicated(corpus):
    def responder(messages):
        if "xếp hạng tài liệu" in messages[0]["content"]:
            return '{"ranking": [3, 3, "3", 1]}'
        return _responder(messages)

    out = _pipeline(corpus, FakeLLM(responder)).run("gcc ra doi nam nao")
    assert out.retrieved_ids[0] == 3
    _assert_valid(out, corpus)


# [3] Lỗi tạm thời: thử lại có backoff, hết lượt thì fallback


def test_transient_classification():
    assert is_transient(StatusError(429)) and is_transient(StatusError(502))
    assert is_transient(APITimeoutError()) and is_transient(ConnectionError())
    assert not is_transient(StatusError(400)) and not is_transient(ValueError())


def test_resilient_llm_retries_transient_errors_then_succeeds():
    attempts, sleeps = [], []

    def flaky(messages):
        attempts.append(1)
        if len(attempts) < 3:
            raise StatusError(429)
        return "ok"

    llm = ResilientLLM(FakeLLM(flaky), retries=2, backoff=5, sleep=sleeps.append)
    assert llm.chat([{"role": "user", "content": "x"}], model="m") == "ok"
    assert sleeps == [5, 15]


def test_resilient_llm_gives_up_and_does_not_retry_bad_request():
    sleeps = []
    llm = ResilientLLM(
        FakeLLM(lambda m: (_ for _ in ()).throw(StatusError(400))), sleep=sleeps.append
    )
    with pytest.raises(LLMUnavailable):
        llm.chat([], model="m")
    assert sleeps == []
    llm = ResilientLLM(
        FakeLLM(lambda m: (_ for _ in ()).throw(APITimeoutError())), sleep=sleeps.append
    )
    with pytest.raises(LLMUnavailable):
        llm.chat([], model="m")
    assert len(sleeps) == 2


def test_resilient_llm_limits_concurrent_requests():
    active, peak, lock = [0], [0], threading.Lock()

    def slow(messages):
        with lock:
            active[0] += 1
            peak[0] = max(peak[0], active[0])
        time.sleep(0.02)
        with lock:
            active[0] -= 1
        return "ok"

    llm = ResilientLLM(FakeLLM(slow), max_concurrent=3)
    threads = [threading.Thread(target=llm.chat, args=([], "m")) for _ in range(12)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert peak[0] <= 3


def test_gateway_down_everywhere_still_returns_valid_output(corpus):
    pipe = _pipeline(corpus, FakeLLM(lambda m: (_ for _ in ()).throw(APITimeoutError())))
    out = pipe.run("clb mm thanh lap khi nao")
    _assert_valid(out, corpus)
    stages = {i["stage"] for i in pipe.last_trace.incidents}
    assert {"rewrite", "rerank", "generate"} <= stages


def test_embedding_failure_drops_dense_signal(corpus):
    pipe = _pipeline(corpus, FakeLLM(_responder))

    class Broken:
        def embed(self, texts):
            raise StatusError(502)

    pipe.retriever.embedder = Broken()
    out = pipe.run("clb mm thanh lap khi nao")
    assert "dense" in {i["stage"] for i in pipe.last_trace.incidents}
    _assert_valid(out, corpus)


# [4] Sinh câu trả lời lỗi


@pytest.mark.parametrize("fault", [StatusError(500), "", "   "])
def test_generation_failure_returns_extract_of_top_doc(corpus, fault):
    def responder(messages):
        if "chuẩn hóa câu hỏi" in messages[0]["content"] or "xếp hạng" in messages[0]["content"]:
            return _responder(messages)
        if isinstance(fault, Exception):
            raise fault
        return fault

    pipe = _pipeline(corpus, FakeLLM(responder))
    out = pipe.run("clb mm thanh lap khi nao")
    top = next(d for d in corpus if d.id == out.retrieved_ids[0])
    assert out.answer == top.text
    assert "generate" in {i["stage"] for i in pipe.last_trace.incidents}


def test_fallback_answer_without_docs_is_refusal():
    assert "không có thông tin" in fallback_answer([])


# [5] Output luôn hợp lệ


def test_clip_answer_cuts_at_sentence_boundary():
    text = "Câu một rất dài. " * 200
    clipped = clip_answer(text)
    assert len(clipped) <= 2000 and clipped.endswith(".")
    assert clip_answer("  ngắn  ") == "ngắn"


def test_sanitize_ids_drops_duplicates_unknown_and_non_numbers():
    assert sanitize_ids([3, "3", 999, None, "x", 1, 2], {1, 2, 3}) == [3, 1, 2]
    assert sanitize_ids(list(range(1, 30)), set(range(1, 30))) == list(range(1, 11))


def test_long_answer_is_clipped(corpus):
    def responder(messages):
        if "chuẩn hóa câu hỏi" in messages[0]["content"] or "xếp hạng" in messages[0]["content"]:
            return _responder(messages)
        return "Một câu trả lời rất dài. " * 300

    out = _pipeline(corpus, FakeLLM(responder)).run("clb mm thanh lap khi nao")
    _assert_valid(out, corpus)


def test_retriever_crash_uses_local_bm25(corpus, monkeypatch):
    pipe = _pipeline(corpus, FakeLLM(_responder))
    monkeypatch.setattr(pipe.retriever, "retrieve", lambda *a, **k: 1 / 0)
    out = pipe.run("gcc ra doi nam nao")
    _assert_valid(out, corpus)
    assert out.retrieved_ids[0] == 3
    assert {"pipeline", "retrieve"} <= {i["stage"] for i in pipe.last_trace.incidents}


# [6] Chạy dở bị ngắt: chạy lại dùng cache, câu đã xong không đổi


class FakeTransport:
    """Thay openai.OpenAI bên trong LLMClient thật (cache SQLite thật), đếm số request ra mạng."""

    def __init__(self):
        self.requests = 0
        self.down = False
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self._chat))
        self.embeddings = SimpleNamespace(create=self._embed)

    def _hit(self):
        if self.down:
            raise ConnectionError("mất kết nối")
        self.requests += 1

    def _chat(self, model, messages):
        self._hit()
        content = _responder(messages)
        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=content))])

    def _embed(self, model, input, encoding_format):
        self._hit()
        vecs = FakeEmbedder().embed(input)
        return SimpleNamespace(
            data=[SimpleNamespace(index=i, embedding=v.tolist()) for i, v in enumerate(vecs)]
        )


def _cached_pipeline(corpus, cache, transport):
    client = LLMClient(api_key="test", base_url="http://fake.local/v1", cache_path=cache)
    client._client = transport
    pipe = SolutionPipeline(PipelineConfig(), llm=client)
    pipe.llm.sleep = lambda s: None
    pipe.index(corpus)
    return pipe


def test_rerun_after_interrupt_reuses_cache_and_keeps_finished_answers(corpus, tmp_path):
    cache = tmp_path / "c.sqlite"
    questions = ["clb mm thanh lap khi nao", "gcc ra doi nam nao", "proptit thanh lap ngay nao"]
    first = _cached_pipeline(corpus, cache, FakeTransport())
    done = [first.run(q) for q in questions[:2]]  # câu thứ 3 chưa chạy thì bị ngắt

    transport = FakeTransport()
    again = _cached_pipeline(corpus, cache, transport)
    transport.down = True  # câu đã xong không được gọi mạng lần nào
    assert [again.run(q) for q in questions[:2]] == done
    assert transport.requests == 0 and not again.last_trace.incidents
    transport.down = False
    _assert_valid(again.run(questions[2]), corpus)
    assert transport.requests > 0


def test_fallback_results_are_not_cached(corpus, tmp_path):
    cache = tmp_path / "c.sqlite"
    transport = FakeTransport()
    pipe = _cached_pipeline(corpus, cache, transport)
    transport.down = True
    degraded = pipe.run("gcc ra doi nam nao")
    assert pipe.last_trace.incidents
    transport.down = False
    healed = pipe.run("gcc ra doi nam nao")
    assert not pipe.last_trace.incidents and healed != degraded


# [7] Log từng câu


def test_log_records_each_question(corpus, tmp_path):
    log = tmp_path / "run_log.jsonl"
    pipe = _pipeline(corpus, _failing("xếp hạng tài liệu", StatusError(503)), log_path=str(log))
    pipe.run("clb mm thanh lap khi nao")
    pipe.run("gcc ra doi nam nao")
    rows = [json.loads(line) for line in log.read_text(encoding="utf-8").splitlines()]
    assert len(rows) == 2
    assert rows[0]["fallback_used"] and rows[0]["incidents"][0]["stage"] == "rerank"
    assert set(rows[0]) >= {"query", "abstained", "answer_chars", "n_ids", "latency_ms"}
    assert np.isfinite(rows[1]["latency_ms"])


def test_cache_path_from_env_gives_independent_cache(monkeypatch, tmp_path):
    monkeypatch.setenv("OPENAI_API_KEY", "test")
    monkeypatch.setenv("RAG_CACHE_PATH", str(tmp_path / "run1" / "cache.sqlite"))
    pipe = SolutionPipeline()
    assert pipe.config.cache_path.endswith("cache.sqlite")
    assert (tmp_path / "run1" / "cache.sqlite").exists()
    monkeypatch.delenv("RAG_CACHE_PATH")
    assert PipelineConfig.from_env().cache_path == ".cache/solution.sqlite"
