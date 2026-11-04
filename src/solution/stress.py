"""Bộ stress cho retrieval: biến thể "khó hơn" của câu hỏi TRAIN, làm proxy cho độ khó của Private Test.

Mỗi câu hỏi được bỏ dấu hoàn toàn rồi thay các cụm phổ biến bằng viết tắt mà sinh viên hay dùng
(dpt, mm/mpc, hv, gcc, clb lap trinh/proptit, tv, sv, ko, dc). Biến đổi là luật tất định, chỉ áp dụng lên
câu hỏi train; không dùng câu hỏi Public/Private.

    python -m solution bench --stress     # đo retrieval trên câu gốc và câu biến thể
"""

from __future__ import annotations

import re

from solution.textproc import fold

# (cụm đã bỏ dấu, [các dạng thay thế]); dạng thay thế chọn luân phiên theo thứ tự câu hỏi để có cả hai.
# Thứ tự quan trọng: cụm dài trước cụm ngắn.
_REPLACEMENTS: list[tuple[str, list[str]]] = [
    ("clb nha sang tao game ptit gcc", ["gcc"]),
    ("clb nha sang tao game ptit", ["gcc"]),
    ("clb nha sang tao game", ["gcc"]),
    ("nha sang tao game", ["gcc"]),
    ("clb multimedia ptit", ["mm", "mpc"]),
    ("clb multimedia", ["clb mm", "mpc"]),
    ("multimedia", ["mm", "mpc"]),
    ("clb lap trinh ptit proptit", ["clb lap trinh", "proptit"]),
    ("clb lap trinh ptit", ["clb lap trinh", "proptit"]),
    ("da phuong tien", ["dpt"]),
    ("hoc vien", ["hv"]),
    ("thanh vien", ["tv"]),
    ("sinh vien", ["sv"]),
    ("khong", ["ko", "k"]),
    ("duoc", ["dc"]),
]


def stress_variant(query: str, index: int = 0) -> str:
    """Câu hỏi không dấu + viết tắt. index chọn luân phiên dạng thay thế."""
    text = f" {fold(query)} "
    for phrase, options in _REPLACEMENTS:
        text = re.sub(rf"(?<= ){re.escape(phrase)}(?= )", options[index % len(options)], text)
    return " ".join(text.split())
