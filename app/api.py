"""API cho chatbot (FastAPI + Server-Sent Events). Chạy:

    uvicorn app.api:app --port 8000          # cài thêm: pip install -e ".[api]"

- POST /api/chat           {"message": "...", "cite": true} → luồng SSE:
      event: stage   {"name": "rewrite|retrieve|rerank|generate", "status": "start|done", "ms"}
      event: token   {"text": "..."}
      event: done    {answer, abstained, citations[], retrieved_ids, trace{...}, latency_ms}
      event: error   {"message": "..."}
- GET  /api/suggestions    câu hỏi gợi ý cho giao diện
- GET  /api/doc/{id}       nội dung một đoạn trong corpus
- GET  /api/health         trạng thái pipeline

Chế độ trích dẫn `[n]` chỉ có ở API chatbot; bài nộp (`neorag run`) dùng `SolutionPipeline.run`, không đổi.
Biến môi trường: NEORAG_CORS_ORIGINS (mặc định "*"), các biến RAG_* như pipeline.
"""

from __future__ import annotations

import json
import os
import queue
import threading
from collections.abc import Iterator
from functools import lru_cache

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from neorag.data import load_corpus
from solution.pipeline import SolutionPipeline
from solution.trace import TracedChat

SUGGESTIONS = [
    {"text": "clb lap trinh ptit thanh lap nam nao, phuong cham la gi", "tag": "không dấu"},
    {"text": "sv nganh dpt nen vao clb nao o hv", "tag": "viết tắt"},
    {"text": "ProPTIT và GCC, CLB nào thành lập trước?", "tag": "so sánh"},
    {"text": "Muốn vào CLB Multimedia PTIT thì cần làm gì?", "tag": "tuyển thành viên"},
    {"text": "GCC có những hoạt động gì cho thành viên?", "tag": "nhiều đoạn"},
    {"text": "Phí thành viên của CLB Multimedia là bao nhiêu?", "tag": "có thể không có đáp án"},
]


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=1000)
    cite: bool = True


@lru_cache(maxsize=1)
def get_chat() -> tuple[TracedChat, dict]:
    """Nạp pipeline và index một lần cho cả tiến trình (embedding corpus lấy từ cache)."""
    corpus = load_corpus()
    pipeline = SolutionPipeline()
    pipeline.index(corpus)
    return TracedChat(pipeline), {d.id: d for d in corpus}


def _sse(kind: str, data: dict) -> str:
    return f"event: {kind}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


def _run_in_thread(chat: TracedChat, message: str, cite: bool) -> Iterator[str]:
    """Chạy toàn bộ pipeline trên MỘT luồng riêng (sổ sự cố và bộ đếm lời gọi theo luồng), đẩy sự kiện qua hàng
    đợi; luồng SSE chỉ đọc hàng đợi. Lỗi không lường trước được trả về dưới dạng event `error`."""
    q: queue.Queue = queue.Queue()
    end = object()

    def worker():
        try:
            for kind, data in chat.stream(message, cite=cite):
                q.put(_sse(kind, data))
        except Exception as exc:  # noqa: BLE001 - không để kết nối treo
            q.put(_sse("error", {"message": f"{type(exc).__name__}: {exc}"}))
        finally:
            q.put(end)

    threading.Thread(target=worker, daemon=True).start()
    while (item := q.get()) is not end:
        yield item


def create_app(chat_factory=get_chat) -> FastAPI:
    app = FastAPI(title="NeoRAG S2B Chatbot API", version="1.0")
    origins = os.getenv("NEORAG_CORS_ORIGINS", "*").split(",")
    app.add_middleware(
        CORSMiddleware, allow_origins=origins, allow_methods=["*"], allow_headers=["*"]
    )

    @app.post("/api/chat")
    def chat(req: ChatRequest):
        traced, _ = chat_factory()
        return StreamingResponse(
            _run_in_thread(traced, req.message.strip(), req.cite),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )

    @app.get("/api/suggestions")
    def suggestions():
        return {"suggestions": SUGGESTIONS}

    @app.get("/api/doc/{doc_id}")
    def doc(doc_id: int):
        _, docs = chat_factory()
        if doc_id not in docs:
            raise HTTPException(404, f"không có đoạn {doc_id}")
        d = docs[doc_id]
        return {"id": d.id, "club": d.club, "topic": d.topic, "text": d.text}

    @app.get("/api/health")
    def health():
        traced, docs = chat_factory()
        pipe = traced.pipe
        return {
            "status": "ok",
            "model": pipe.llm_model,
            "corpus_size": len(docs),
            "rerank": pipe.config.retrieval.use_rerank,
            "prompt": pipe.config.prompt,
        }

    return app


app = create_app()
