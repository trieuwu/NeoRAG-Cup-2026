"""Bộ hard-dev: câu hỏi khó sinh TỪ CORPUS (không dùng câu Public/Private), làm thước đo retrieval.

Train dễ hơn Public nhiều (Retrieval E7: train 98.6, Public 93.8), nên cần một bộ đo gần Public hơn.
Mỗi câu được sinh từ một nhóm 1-3 đoạn chọn bằng luật cố định (seed), relevant_ids = đúng nhóm đó:
- so sánh: 2 đoạn cùng chủ đề của 2 CLB khác nhau;
- nhiều đoạn: 2-3 đoạn của cùng một CLB, gần nhau về nội dung (bge-m3) nhưng khác đoạn;
- thời gian: 1-2 đoạn có mốc ngày/năm;
Văn phong sinh viên: một nửa viết không dấu/viết tắt.

Lọc mơ hồ tự động: Haiku (lời gọi thứ hai, độc lập) đọc câu hỏi + nhóm đoạn + 6 đoạn gây nhiễu gần nhất
về nội dung, liệt kê các đoạn cần để trả lời. Chỉ giữ câu mà tập đoạn được chọn TRÙNG KHỚP nhóm gốc: thiếu
đoạn (câu không cần đủ nhóm) hay thừa đoạn (đoạn gây nhiễu cũng trả lời được) đều bị loại. Cờ "ambiguous"
của Haiku bật ở 2/3 số câu kể cả khi tập đoạn khớp đúng (lần chạy đầu), nên chỉ ghi lại, không dùng để loại.

    python -m solution harddev        # ghi data/solution/hard_dev.jsonl
"""

from __future__ import annotations

import json
import random
import re
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from neorag.data import Document

HARD_DEV_PATH = Path("data/solution/hard_dev.jsonl")
_DATE = re.compile(r"\b(?:\d{1,2}/\d{1,2}/\d{4}|\d{1,2}/\d{4}|(?:19|20)\d{2})\b")

KINDS = {
    "so sánh": "so sánh giữa hai CLB (ví dụ CLB nào ..., hai CLB khác nhau thế nào về ...)",
    "nhiều đoạn": "hỏi gộp nhiều ý trong cùng một câu, các ý nằm ở các đoạn khác nhau",
    "thời gian": "hỏi về mốc thời gian, thứ tự trước sau hoặc khoảng thời gian",
}
STYLES = {
    "có dấu": "tiếng Việt có dấu nhưng tự nhiên, kiểu sinh viên nhắn tin hỏi (có thể dùng tên gọi tắt như ProPTIT, MPC, GCC)",
    "không dấu": "KHÔNG DẤU toàn bộ, kiểu sinh viên nhắn tin vội, dùng viết tắt (vd. clb, sv, hv, ko, dc, mm/mpc, gcc, dpt, proptit/clb lap trinh)",
}

GEN_SYSTEM = """Bạn tạo câu hỏi kiểm thử cho hệ thống tìm kiếm tài liệu về cộng đồng S2B tại PTIT (CLB Lập Trình PTIT, CLB Multimedia PTIT, CLB Nhà Sáng Tạo Game PTIT).
Cho các đoạn tài liệu có mã [id]. Viết MỘT câu hỏi mà muốn trả lời ĐẦY ĐỦ phải dùng thông tin từ TẤT CẢ các đoạn đã cho (mỗi đoạn đóng góp ít nhất một ý mà đoạn khác không có).
Yêu cầu:
- Kiểu câu hỏi: {kind}.
- Văn phong: {style}.
- Câu hỏi phải rõ ràng, chỉ có một cách hiểu, nêu rõ CLB được hỏi (có thể bằng tên gọi tắt).
- Không nhắc tới "đoạn", "tài liệu", mã id. Không chép nguyên câu trong đoạn: diễn đạt như người hỏi thật.
- Nếu không thể viết câu hỏi tự nhiên cần đủ mọi đoạn, trả {{"ok": false}}.
Chỉ trả về JSON: {{"ok": true, "question": "...", "needs": {{"<id>": "ý lấy từ đoạn này"}}}}"""

VERIFY_SYSTEM = """Bạn kiểm tra câu hỏi kiểm thử cho hệ thống tìm kiếm tài liệu về các CLB tại PTIT.
Cho một câu hỏi và các đoạn tài liệu có mã [id]. Liệt kê TẤT CẢ id các đoạn chứa thông tin CẦN để trả lời đầy đủ câu hỏi (bỏ các đoạn không cần).
Đánh dấu "ambiguous": true nếu câu hỏi có thể hiểu theo nhiều cách, hoặc có đoạn khác ngoài các đoạn cần cũng trả lời được cùng một ý.
Chỉ trả về JSON: {"ids": [id, ...], "ambiguous": false}"""


@dataclass
class Candidate:
    kind: str
    style: str
    ids: list[int]


def _date_docs(docs: list[Document]) -> list[int]:
    return [i for i, d in enumerate(docs) if _DATE.search(d.text)]


def sample_groups(docs: list[Document], vectors: np.ndarray, n: int, seed: int = 2026):
    """Chọn nhóm đoạn theo luật cố định (không nhìn vào câu hỏi Public/Private)."""
    rng = random.Random(seed)
    sims = vectors @ vectors.T
    by_topic: dict[str, dict[str, list[int]]] = {}
    for i, d in enumerate(docs):
        by_topic.setdefault(d.topic, {}).setdefault(d.club, []).append(i)
    shared = [t for t, clubs in by_topic.items() if len(clubs) >= 2]
    dated = _date_docs(docs)

    def neighbours(i: int, same_club: bool, k: int = 4) -> list[int]:
        order = [int(j) for j in np.argsort(-sims[i]) if j != i]
        return [j for j in order if (docs[j].club == docs[i].club) == same_club][:k]

    out: list[Candidate] = []
    seen: set[tuple[int, ...]] = set()
    kinds = list(KINDS)
    while len(out) < n:
        kind = kinds[len(out) % len(kinds)]
        if kind == "so sánh":
            topic = rng.choice(shared)
            a, b = rng.sample(sorted(by_topic[topic]), 2)
            ids = [rng.choice(by_topic[topic][a]), rng.choice(by_topic[topic][b])]
        elif kind == "nhiều đoạn":
            i = rng.randrange(len(docs))
            ids = [i, *rng.sample(neighbours(i, True), rng.choice([1, 2]))]
        else:
            i = rng.choice(dated)
            near = [j for j in neighbours(i, True, 6) if j in dated]
            ids = [i] + ([rng.choice(near)] if near and rng.random() < 0.6 else [])
        key = tuple(sorted(ids))
        if key in seen:
            continue
        seen.add(key)
        out.append(Candidate(kind, "không dấu" if len(out) % 2 else "có dấu", list(key)))
    return out


def _context(docs: list[Document], idx: list[int]) -> str:
    return "\n\n".join(
        f"[{docs[i].id}] ({docs[i].club} | {docs[i].topic})\n{docs[i].text}" for i in idx
    )


def _json(reply: str) -> dict:
    start, end = reply.find("{"), reply.rfind("}")
    try:
        data = json.loads(reply[start : end + 1]) if start >= 0 else {}
    except json.JSONDecodeError:
        return {}
    return data if isinstance(data, dict) else {}


def build(
    docs: list[Document], vectors: np.ndarray, llm, model: str, n: int = 130, workers: int = 6
):
    """Sinh + lọc. Trả về (danh sách câu giữ lại, thống kê lý do loại)."""
    cands = sample_groups(docs, vectors, n)
    sims = vectors @ vectors.T
    stats = {"sinh lỗi/không viết được": 0, "thiếu đoạn": 0, "thừa/sai đoạn": 0}

    def one(c: Candidate):
        system = GEN_SYSTEM.format(kind=KINDS[c.kind], style=STYLES[c.style])
        user = _context(docs, c.ids)
        gen = _json(
            llm.chat(
                [{"role": "system", "content": system}, {"role": "user", "content": user}],
                model=model,
            )
        )
        question = gen.get("question")
        if not gen.get("ok") or not isinstance(question, str) or not question.strip():
            return None, "sinh lỗi/không viết được"
        group = set(c.ids)
        distract = [int(j) for j in np.argsort(-sims[c.ids].max(axis=0)) if int(j) not in group][:6]
        shown = sorted([*c.ids, *distract], key=lambda j: docs[j].id)
        ver = _json(
            llm.chat(
                [
                    {"role": "system", "content": VERIFY_SYSTEM},
                    {
                        "role": "user",
                        "content": f"CÂU HỎI: {question}\n\nTÀI LIỆU:\n{_context(docs, shown)}",
                    },
                ],
                model=model,
            )
        )
        picked = {int(i) for i in ver.get("ids", []) if str(i).isdigit()}
        wanted = {docs[i].id for i in c.ids}
        if picked < wanted:
            return None, "thiếu đoạn"
        if picked != wanted:
            return None, "thừa/sai đoạn"
        return {
            "query": question.strip(),
            "relevant_ids": sorted(docs[i].id for i in c.ids),
            "type": c.kind,
            "style": c.style,
            "flagged_ambiguous": bool(ver.get("ambiguous")),
            "answerable": True,
        }, None

    with ThreadPoolExecutor(workers) as pool:
        results = list(pool.map(one, cands))
    kept = []
    for row, reason in results:
        if row is None:
            stats[reason] += 1
        else:
            kept.append({"id": f"hd-{len(kept) + 1:03d}", **row})
    return kept, stats


def save(rows: list[dict], path: Path = HARD_DEV_PATH) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), encoding="utf-8"
    )
