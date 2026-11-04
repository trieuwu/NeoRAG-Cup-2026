"""Synthetic Question Anchors (doc2query): mỗi đoạn văn có một bộ câu hỏi giả định và thực thể chính.

Câu hỏi của sinh viên ngắn, văn nói, hay không dấu; đoạn văn là văn xuôi dài. Truy xuất "câu hỏi ↔ câu
hỏi giả định" bớt lệch hơn "câu hỏi ↔ đoạn văn" (asymmetric search). Anchors chỉ sinh từ NỘI DUNG CORPUS
bằng claude-haiku-5-5, không dùng bất kỳ câu hỏi nào của bộ train/test.

Sinh một lần rồi lưu vào data/solution/doc_anchors.jsonl (commit vào repo) để mọi lần chạy, kể cả ngày
Private Test, dùng đúng cùng một bộ anchors:
    python -m solution anchors
"""

from __future__ import annotations

import json
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from pathlib import Path

from neorag.data import DATA_DIR, Document
from neorag.llm import LLMClient

ANCHORS_PATH = DATA_DIR / "solution" / "doc_anchors.jsonl"

ANCHOR_SYSTEM = """Bạn hỗ trợ xây chỉ mục tìm kiếm cho chatbot hỏi đáp về cộng đồng S2B tại PTIT.
Cho MỘT đoạn tài liệu, hãy liệt kê những câu hỏi mà sinh viên có thể hỏi và đoạn này trả lời được.

Yêu cầu:
- "questions": 8 câu hỏi khác nhau, mỗi câu hỏi một khía cạnh có trong đoạn (con số, ngày, tên người, tên ban, quy định, sự kiện...).
  + 5 câu viết tiếng Việt có dấu, tự nhiên, ngắn như sinh viên hỏi; dùng nhiều cách gọi tên CLB khác nhau
    (tên đầy đủ, ProPTIT / "clb lập trình", Multimedia / MPC / "mm", GCC / "clb game").
  + 3 câu viết KHÔNG DẤU kiểu nhắn tin, có viết tắt quen thuộc (ko, dc, tv, hv, nk, e...).
- "entities": tối đa 8 thực thể/từ khóa quan trọng nhất của đoạn (tên riêng, tên ban, tên sự kiện, mốc thời gian, con số kèm đơn vị).
- Chỉ dùng thông tin có trong đoạn. Không trả lời câu hỏi.

Chỉ trả về một object JSON: {"questions": ["..."], "entities": ["..."]}"""


@dataclass
class DocAnchors:
    id: int
    questions: list[str] = field(default_factory=list)
    entities: list[str] = field(default_factory=list)

    def text(self) -> str:
        return "\n".join([*self.questions, " ; ".join(self.entities)])


def _parse(doc_id: int, reply: str) -> DocAnchors:
    start, end = reply.find("{"), reply.rfind("}")
    try:
        data = json.loads(reply[start : end + 1]) if start >= 0 else {}
    except json.JSONDecodeError:
        data = {}
    qs = [q.strip() for q in data.get("questions") or [] if isinstance(q, str) and q.strip()]
    es = [e.strip() for e in data.get("entities") or [] if isinstance(e, str) and e.strip()]
    return DocAnchors(doc_id, qs[:10], es[:10])


def generate(
    corpus: list[Document], llm: LLMClient, model: str, workers: int = 6
) -> list[DocAnchors]:
    def one(d: Document) -> DocAnchors:
        reply = llm.chat(
            [
                {"role": "system", "content": ANCHOR_SYSTEM},
                {"role": "user", "content": f"({d.club} | {d.topic})\n{d.text}"},
            ],
            model=model,
        )
        return _parse(d.id, reply)

    with ThreadPoolExecutor(workers) as pool:
        return list(pool.map(one, corpus))


def save(anchors: list[DocAnchors], path: Path = ANCHORS_PATH) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        for a in anchors:
            f.write(json.dumps(a.__dict__, ensure_ascii=False) + "\n")


def load(path: Path = ANCHORS_PATH) -> dict[int, DocAnchors]:
    if not Path(path).exists():
        return {}
    out = {}
    with open(path, encoding="utf-8") as f:
        for line in f:
            if line.strip():
                row = json.loads(line)
                out[int(row["id"])] = DocAnchors(int(row["id"]), row["questions"], row["entities"])
    return out
