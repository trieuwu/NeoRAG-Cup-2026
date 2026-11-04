"""Hiểu câu hỏi bằng claude-haiku-5-5: thêm dấu, mở rộng viết tắt, nhận diện CLB, tách ý.

Một lời gọi LLM cho mỗi câu hỏi, kết quả được cache bởi LLMClient. Nếu LLM trả về JSON lỗi,
pipeline vẫn chạy tiếp với câu hỏi gốc (không bao giờ làm hỏng cả lượt chạy).
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field

from neorag.llm import LLMClient

# Khóa CLB chuẩn -> giá trị trường `club` trong data/corpus.jsonl
CLUBS: dict[str, str] = {
    "proptit": "CLB Lập Trình PTIT",
    "multimedia": "CLB Multimedia PTIT",
    "gcc": "CLB Nhà Sáng Tạo Game PTIT (GCC)",
    "s2b": "Cộng đồng S2B",
}

REWRITE_SYSTEM = """Bạn chuẩn hóa câu hỏi của sinh viên gửi tới chatbot của cộng đồng S2B tại Học viện Công nghệ Bưu chính Viễn thông (PTIT).
S2B gồm 3 CLB:
- proptit: CLB Lập Trình PTIT (PROPTIT, ProPTIT, "clb lập trình", "clb lt", "pro").
- multimedia: CLB Multimedia PTIT (MPC, "mm", CLB Sáng tạo Đa phương tiện; hợp với sinh viên ngành Đa phương tiện - "dpt": thiết kế, chụp ảnh, quay dựng, truyền thông).
- gcc: CLB Nhà Sáng Tạo Game PTIT (GCC, Game Creators Club, "clb game", "clb làm game").
- s2b: cộng đồng chung của cả 3 CLB (sự kiện chung, sinh nhật chung, quan hệ giữa các CLB).
Viết tắt thường gặp: hv = Học viện, nk = nhiệm kỳ, bcn = ban chủ nhiệm, tv = thành viên, sv = sinh viên, ko/k/kh = không, dc = được, e = em.

Nhiệm vụ (KHÔNG trả lời câu hỏi):
1. "query": viết lại câu hỏi thành tiếng Việt có dấu đầy đủ, rõ ràng, mở rộng mọi viết tắt, ghi rõ tên đầy đủ của CLB. Giữ nguyên mọi ý được hỏi, không thêm ý mới.
2. "clubs": danh sách khóa CLB mà câu hỏi nhắc tới, chọn trong ["proptit", "multimedia", "gcc", "s2b"]. Để [] nếu không rõ.
3. "sub_queries": nếu câu hỏi gồm nhiều ý hoặc so sánh nhiều CLB, tách thành các câu hỏi con có dấu, mỗi câu một ý (tối đa 3). Câu hỏi một ý thì để [].

Chỉ trả về một object JSON đúng dạng sau, không giải thích:
{"query": "...", "clubs": ["..."], "sub_queries": ["..."]}"""

_JSON_OBJECT = re.compile(r"\{.*\}", re.DOTALL)


@dataclass
class QueryPlan:
    original: str
    rewritten: str
    clubs: list[str] = field(default_factory=list)  # khóa trong CLUBS
    sub_queries: list[str] = field(default_factory=list)

    @property
    def club_names(self) -> set[str]:
        return {CLUBS[c] for c in self.clubs}


def parse_plan(original: str, reply: str) -> QueryPlan:
    """Đọc JSON từ câu trả lời của LLM; lỗi thì trả về plan chỉ chứa câu hỏi gốc."""
    match = _JSON_OBJECT.search(reply or "")
    try:
        data = json.loads(match.group()) if match else {}
    except json.JSONDecodeError:
        data = {}
    if not isinstance(data, dict):
        data = {}
    rewritten = data.get("query")
    rewritten = rewritten.strip() if isinstance(rewritten, str) and rewritten.strip() else original
    clubs = [c for c in data.get("clubs") or [] if isinstance(c, str) and c in CLUBS]
    subs = [s.strip() for s in data.get("sub_queries") or [] if isinstance(s, str) and s.strip()]
    return QueryPlan(original, rewritten, list(dict.fromkeys(clubs)), subs[:3])


class QueryRewriter:
    def __init__(self, llm: LLMClient, model: str):
        self.llm, self.model = llm, model

    def __call__(self, query: str) -> QueryPlan:
        reply = self.llm.chat(
            [
                {"role": "system", "content": REWRITE_SYSTEM},
                {"role": "user", "content": query},
            ],
            model=self.model,
        )
        return parse_plan(query, reply)
