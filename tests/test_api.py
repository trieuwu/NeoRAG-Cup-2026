"""API chatbot: trace từng bước, SSE, và không làm đổi output của bài nộp. Không gọi gateway."""

from __future__ import annotations

import json

import pytest

from conftest import FakeEmbedder, FakeLLM
from solution.pipeline import PipelineConfig, SolutionPipeline
from solution.trace import TracedChat, expansions


def _responder(messages):
    system = messages[0]["content"]
    if "chuẩn hóa câu hỏi" in system:
        return json.dumps(
            {"query": "CLB Multimedia PTIT thành lập khi nào?", "clubs": ["multimedia"]}
        )
    if "xếp hạng tài liệu" in system:
        return json.dumps({"ranking": [2, 1]})
    if "CHẾ ĐỘ TRÍCH DẪN" in system:
        return "CLB Multimedia PTIT thành lập ngày 10/11/2012 [1]."
    return "CLB Multimedia PTIT thành lập ngày 10/11/2012."


def _pipeline(corpus):
    pipe = SolutionPipeline(PipelineConfig(), llm=FakeLLM(_responder))
    pipe.retriever.embedder = FakeEmbedder()
    pipe.index(corpus)
    return pipe


def _stream_pipeline(corpus):
    pipe = _pipeline(corpus)

    class Completions:
        def create(self, model, messages, stream):
            text = _responder(messages)
            for word in text.split(" "):
                delta = type("D", (), {"content": word + " "})
                yield type("C", (), {"choices": [type("Ch", (), {"delta": delta})]})

    inner = pipe.llm.inner
    inner._client = type("Client", (), {"chat": type("Chat", (), {"completions": Completions()})})()
    inner._cache = None
    inner._endpoint = "fake"
    return pipe


def test_traced_chat_matches_submission_pipeline(corpus):
    pipe = _stream_pipeline(corpus)
    expected = _pipeline(corpus).run("clb mm thanh lap khi nao")
    events = list(TracedChat(pipe).stream("clb mm thanh lap khi nao", cite=False))
    kinds = [k for k, _ in events]
    assert kinds[0] == "stage" and kinds[-1] == "done" and "token" in kinds
    stages = [(d["name"], d["status"]) for k, d in events if k == "stage"]
    assert stages == [
        (n, s) for n in ("rewrite", "retrieve", "rerank", "generate") for s in ("start", "done")
    ]
    done = events[-1][1]
    assert done["retrieved_ids"] == expected.retrieved_ids  # cùng tài liệu với bài nộp
    assert done["answer"] == expected.answer
    trace = done["trace"]
    assert trace["rewritten_query"] == "CLB Multimedia PTIT thành lập khi nào?"
    assert {"from": "mm", "to": "multimedia"} in trace["expansions"]
    assert any(c["selected"] for c in trace["candidates"])
    assert {s["name"] for s in trace["stages"]} == {"rewrite", "retrieve", "rerank", "generate"}
    assert trace["llm_calls"] >= 2


def test_cite_mode_only_changes_chatbot_answer(corpus):
    pipe = _stream_pipeline(corpus)
    done = list(TracedChat(pipe).stream("clb mm thanh lap khi nao", cite=True))[-1][1]
    assert done["answer"].endswith("[1].")
    assert done["citations"][0]["n"] == 1 and done["citations"][0]["cited"]
    assert not _pipeline(corpus).run("clb mm thanh lap khi nao").answer.endswith("[1].")


def test_expansions_lists_abbreviations():
    out = expansions("sv nganh dpt vao mm dc ko")
    assert {"from": "dpt", "to": "da phuong tien multimedia"} in out
    assert len({e["from"] for e in out}) == len(out)


fastapi = pytest.importorskip("fastapi")


def test_api_endpoints_and_sse(corpus):
    from app.api import create_app
    from fastapi.testclient import TestClient

    pipe = _stream_pipeline(corpus)
    chat = TracedChat(pipe)
    client = TestClient(create_app(lambda: (chat, {d.id: d for d in corpus})))
    assert client.get("/api/health").json()["corpus_size"] == 3
    assert client.get("/api/doc/2").json()["club"] == "CLB Multimedia PTIT"
    assert client.get("/api/doc/999").status_code == 404
    assert client.get("/api/suggestions").json()["suggestions"]
    with client.stream("POST", "/api/chat", json={"message": "clb mm thanh lap khi nao"}) as r:
        assert r.headers["content-type"].startswith("text/event-stream")
        body = "".join(r.iter_text())
    kinds = [line[7:] for line in body.splitlines() if line.startswith("event: ")]
    assert kinds[-1] == "done" and "token" in kinds and "stage" in kinds
    done = json.loads(body.strip().split("data: ")[-1])
    assert done["citations"] and "trace" in done
    assert client.post("/api/chat", json={"message": ""}).status_code == 422


# ---------------------------------------------------------------- hợp đồng với giao diện


class StatusError(Exception):
    def __init__(self, status_code):
        super().__init__(f"HTTP {status_code}")
        self.status_code = status_code


def test_candidates_have_club_topic_and_rank_fields(corpus):
    done = list(TracedChat(_stream_pipeline(corpus)).stream("clb mm thanh lap khi nao"))[-1][1]
    cand = done["trace"]["candidates"]
    assert len(cand) == min(20, len(corpus))
    assert set(cand[0]) == {
        "id", "club", "topic", "bm25_rank", "dense_rank", "rerank_rank", "selected"
    }  # fmt: skip
    assert all(c["rerank_rank"] is None or c["rerank_rank"] >= 1 for c in cand)


def test_cache_hit_true_only_when_every_call_is_cached(corpus):
    from neorag.llm import _key

    class DictCache(dict):
        def set(self, k, v):
            self[k] = v

    class CachingLLM(FakeLLM):
        """Như LLMClient: tra cache trước, ghi cache sau khi gọi."""

        _endpoint = "fake"

        def __init__(self):
            super().__init__(_responder)
            self._cache = DictCache()

        def chat(self, messages, model, temperature=None):
            key = _key("chat", self._endpoint, model, None, messages)
            if key not in self._cache:
                self._cache.set(key, super().chat(messages, model))
            return self._cache[key]

    pipe = SolutionPipeline(PipelineConfig(), llm=CachingLLM())
    pipe.retriever.embedder = FakeEmbedder()
    pipe.index(corpus)
    pipe.llm.inner._client = _stream_pipeline(corpus).llm.inner._client
    chat = TracedChat(pipe)
    first = list(chat.stream("clb mm thanh lap khi nao"))[-1][1]["trace"]
    second = list(chat.stream("clb mm thanh lap khi nao"))[-1][1]["trace"]
    assert not first["cache_hit"] and first["llm_cache_hits"] < first["llm_calls"]
    assert second["cache_hit"] and second["llm_cache_hits"] == second["llm_calls"] == 3


@pytest.mark.parametrize(
    "answer, refused",
    [
        ("Tài liệu hiện có không có thông tin về phí thành viên của CLB Multimedia PTIT.", True),
        ("Tài liệu không đề cập đến học phí.", True),
        (
            "CLB Multimedia PTIT thành lập ngày 10/11/2012 [1]. Tài liệu không đề cập người sáng lập.",
            False,
        ),
        (
            "CLB Multimedia PTIT thành lập ngày 10/11/2012. Tài liệu không có thông tin về phí.",
            False,
        ),
        ("Tài liệu không có thông tin về phí, nhưng CLB tuyển thành viên vào tháng 9 [2].", False),
    ],
)
def test_is_refusal_first_sentence_and_no_citation(answer, refused):
    from solution.trace import is_refusal

    assert is_refusal(answer) is refused


@pytest.mark.parametrize(
    "reply, abstained",
    [
        ("Tài liệu hiện có không có thông tin về phí thành viên.", True),
        (
            "CLB Multimedia PTIT thành lập ngày 10/11/2012 [1]. Tài liệu không đề cập phí thành viên.",
            False,
        ),
    ],
)
def test_done_abstained_for_refusal_but_not_partial_answer(corpus, reply, abstained):
    pipe = _stream_pipeline(corpus)

    class Completions:
        def create(self, model, messages, stream):
            yield type(
                "C", (), {"choices": [type("Ch", (), {"delta": type("D", (), {"content": reply})})]}
            )

    pipe.llm.inner._client = type(
        "Client", (), {"chat": type("Chat", (), {"completions": Completions()})}
    )()
    done = list(TracedChat(pipe).stream("phi thanh vien mm"))[-1][1]
    assert done["abstained"] is abstained
    assert len(done["citations"]) == 3  # vẫn trả các đoạn gần nhất kể cả khi từ chối


def test_incident_events_for_retry_then_fallback(corpus):
    def responder(messages):
        if "xếp hạng tài liệu" in messages[0]["content"]:
            raise StatusError(503)
        return _responder(messages)

    pipe = _stream_pipeline(corpus)
    pipe.llm.inner.responder = responder
    pipe.llm.backoff = 0.001
    got = []
    events = list(
        TracedChat(pipe).stream(
            "clb mm thanh lap khi nao", on_event=lambda k, d: got.append((k, d))
        )
    )
    retries = [d for k, d in got if k == "incident" and d["type"] == "retry"]
    fallbacks = [d for k, d in got if k == "incident" and d["type"] == "fallback"]
    assert [(d["stage"], d["attempt"]) for d in retries] == [("rerank", 1), ("rerank", 2)]
    assert retries[0]["wait_s"] == pytest.approx(0.001)
    assert fallbacks and fallbacks[0]["stage"] == "rerank" and "error" in fallbacks[0]
    assert events[-1][0] == "done"


def test_cancel_stops_between_stages_without_done(corpus):
    import threading

    cancel = threading.Event()
    kinds = []
    for kind, data in TracedChat(_stream_pipeline(corpus)).stream(
        "clb mm thanh lap khi nao", cancel=cancel
    ):
        kinds.append((kind, data.get("name"), data.get("status")))
        if data.get("name") == "rewrite" and data.get("status") == "done":
            cancel.set()
    assert kinds[-1] == ("stage", "rewrite", "done") and "done" not in [k for k, *_ in kinds]


def _client(corpus, pipe=None):
    from app.api import create_app
    from fastapi.testclient import TestClient

    chat = TracedChat(pipe or _stream_pipeline(corpus))
    return TestClient(create_app(lambda: (chat, {d.id: d for d in corpus})))


@pytest.mark.parametrize("message, status", [("   ", 422), ("x" * 501, 422), ("  hi  ", 200)])
def test_message_validation(corpus, message, status):
    pytest.importorskip("fastapi")
    assert _client(corpus).post("/api/chat", json={"message": message}).status_code == status


def test_ping_sent_while_waiting(corpus, monkeypatch):
    pytest.importorskip("fastapi")
    import time

    import app.api as api

    monkeypatch.setattr(api, "PING_S", 0.05)
    pipe = _stream_pipeline(corpus)
    pipe.llm.inner.responder = lambda m: time.sleep(0.3) or _responder(m)
    body = _client(corpus, pipe).post("/api/chat", json={"message": "clb mm"}).text
    assert "event: ping" in body and body.rstrip().splitlines()[-2] == "event: done"
