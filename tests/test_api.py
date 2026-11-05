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
