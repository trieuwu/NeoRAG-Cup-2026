"""Chống lỗi khi chạy thật (Private Test): pipeline không bao giờ ném exception ra `neorag predict`.

- `ResilientLLM` bọc `neorag.llm.LLMClient`: giới hạn số request đồng thời, thử lại có backoff khi gặp lỗi
  tạm thời (429, timeout, 5xx, mất kết nối) sau khi openai SDK đã tự thử lại, hết lượt thì ném
  `LLMUnavailable` để từng bước của pipeline chuyển sang phương án dự phòng. Không đổi nội dung message
  nên khóa cache của LLMClient giữ nguyên (chạy lại tận dụng cache, câu đã xong cho kết quả y hệt).
- `incidents`: sổ ghi lỗi theo từng luồng; pipeline mở sổ ở đầu `run()` và đọc lại ở cuối để ghi log.
- `fallback_answer`, `sanitize_ids`, `clip_answer`: bảo đảm output luôn hợp lệ theo `configs/eval.toml`.
"""

from __future__ import annotations

import json
import re
import threading
import time
from collections.abc import Callable
from pathlib import Path

MAX_CONCURRENT = 8  # giới hạn của gateway BTC
MAX_ANSWER_CHARS = 2000  # configs/eval.toml [submission]
MAX_IDS = 10
REFUSAL = "Tài liệu hiện có không có thông tin để trả lời câu hỏi này."

_TRANSIENT_NAMES = {
    "APIConnectionError",
    "APITimeoutError",
    "RateLimitError",
    "InternalServerError",
    "ConnectionError",
    "TimeoutError",
    "ReadTimeout",
    "ConnectTimeout",
}


class LLMUnavailable(RuntimeError):
    """Gateway không trả lời được sau mọi lần thử: bước gọi LLM phải dùng phương án dự phòng."""


def is_transient(exc: BaseException) -> bool:
    """Lỗi đáng thử lại: 429, 5xx, timeout, mất kết nối. Lỗi 4xx khác (vd. 400) thử lại cũng vô ích."""
    status = getattr(exc, "status_code", None)
    if isinstance(status, int):
        return status == 429 or status == 408 or status >= 500
    return any(cls.__name__ in _TRANSIENT_NAMES for cls in type(exc).__mro__)


# ---------------------------------------------------------------- sổ ghi lỗi theo luồng

_local = threading.local()


def start_incidents() -> None:
    _local.items = []


def record(stage: str, error: BaseException | str) -> None:
    """Ghi một sự cố (bước, mô tả lỗi) cho câu hỏi đang chạy trên luồng hiện tại."""
    if not hasattr(_local, "items"):
        _local.items = []
    text = error if isinstance(error, str) else f"{type(error).__name__}: {error}"
    _local.items.append({"stage": stage, "error": text[:300]})


def collect_incidents() -> list[dict]:
    items = getattr(_local, "items", [])
    _local.items = []
    return items


# ---------------------------------------------------------------- LLM có thử lại


class ResilientLLM:
    """Bọc LLMClient (hoặc client giả trong test) với cùng interface `chat` / `embed`."""

    def __init__(
        self,
        inner,
        retries: int = 2,
        backoff: float = 5.0,
        sleep: Callable[[float], None] = time.sleep,
        max_concurrent: int = MAX_CONCURRENT,
    ):
        self.inner = inner
        self.retries, self.backoff, self.sleep = retries, backoff, sleep
        self._slots = threading.BoundedSemaphore(max_concurrent)

    def __getattr__(self, name):  # thuộc tính khác (cache, endpoint...) lấy từ client gốc
        return getattr(self.inner, name)

    def _call(self, stage: str, fn: Callable[[], object]):
        for attempt in range(self.retries + 1):
            try:
                with self._slots:
                    return fn()
            except Exception as exc:  # noqa: BLE001 - mọi lỗi đều phải được chặn tại đây
                if not is_transient(exc) or attempt == self.retries:
                    raise LLMUnavailable(f"{stage}: {exc}") from exc
                self.sleep(self.backoff * 3**attempt)  # 5s, 15s (sau các lần thử của openai SDK)
        raise AssertionError("unreachable")

    def chat(self, messages: list[dict], model: str, **kwargs) -> str:
        return self._call("chat", lambda: self.inner.chat(messages, model=model, **kwargs))

    def embed(self, texts: list[str], model: str, **kwargs):
        return self._call("embed", lambda: self.inner.embed(texts, model=model, **kwargs))


# ---------------------------------------------------------------- output luôn hợp lệ

_SENTENCE_END = re.compile(r"(?<=[.!?…])\s+")


def clip_answer(text: str, limit: int = MAX_ANSWER_CHARS) -> str:
    """Cắt câu trả lời dài quá giới hạn tại ranh giới câu gần nhất (không cắt giữa chữ)."""
    text = (text or "").strip()
    if len(text) <= limit:
        return text
    head = text[:limit]
    cut = max((m.start() for m in _SENTENCE_END.finditer(head)), default=-1)
    if cut < limit // 2:
        cut = head.rfind(" ")
    return head[: cut if cut > 0 else limit].rstrip()


def fallback_answer(docs) -> str:
    """Câu trả lời khi bước sinh câu trả lời hỏng hẳn: trích nguyên văn 1-2 câu đầu của đoạn đứng đầu.

    Chép từ tài liệu nên có căn cứ (Groundedness) và thường chứa key fact; câu từ chối chung chung sẽ bị
    tính 0 điểm Groundedness ở mọi câu có đáp án. Không có đoạn nào thì mới từ chối.
    """
    if not docs:
        return REFUSAL
    sentences = _SENTENCE_END.split(docs[0].text.strip())
    out = sentences[0]
    if len(sentences) > 1 and len(out) < 160:
        out += " " + sentences[1]
    return clip_answer(out, 600) or REFUSAL


def sanitize_ids(ids, valid: set[int], n: int = MAX_IDS) -> list[int]:
    """Giữ thứ tự, bỏ id trùng, id không có trong corpus, id không phải số; tối đa n id."""
    out: list[int] = []
    for i in ids:
        try:
            i = int(i)
        except (TypeError, ValueError):
            continue
        if i in valid and i not in out:
            out.append(i)
        if len(out) == n:
            break
    return out


def is_abstention(answer: str) -> bool:
    a = answer.lower()
    return "không có thông tin" in a or "không đề cập" in a


# ---------------------------------------------------------------- log từng câu

_log_lock = threading.Lock()


def append_log(path: str | Path, row: dict) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    with _log_lock, p.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")
