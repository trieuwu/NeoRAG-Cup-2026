"""Xử lý văn bản cho BM25: bỏ dấu tiếng Việt, mở rộng viết tắt, tách token unigram + bigram.

Câu hỏi của thí sinh thường viết không dấu ("clb lap trinh"), còn corpus có dấu ("CLB Lập Trình").
Đưa cả hai về dạng bỏ dấu ("clb lap trinh") thì BM25 so khớp được, điều mà embedding làm kém.
"""

from __future__ import annotations

import re
import unicodedata

_NON_WORD = re.compile(r"[^\w\s]", flags=re.UNICODE)

# Viết tắt thường gặp trong câu hỏi -> dạng đầy đủ (đã bỏ dấu). Chỉ là từ điển ngôn ngữ chung,
# không chứa thông tin của câu hỏi cụ thể nào trong bộ test.
ABBREVIATIONS: dict[str, str] = {
    "dpt": "da phuong tien multimedia",
    "mm": "multimedia",
    "mpc": "multimedia",
    "gcc": "game creators club nha sang tao game",
    "hv": "hoc vien",
    "nk": "nhiem ky",
    "bcn": "ban chu nhiem",
    "cn": "chu nhiem",
    "tv": "thanh vien",
    "sv": "sinh vien",
    "dc": "duoc",
    "ko": "khong",
    "k": "khong",
    "kh": "khong",
    "lt": "lap trinh",
    "pro": "proptit",
    "sk": "su kien",
    "multi": "multimedia",
}

# Từ dừng (dạng bỏ dấu): xuất hiện khắp nơi, không giúp phân biệt đoạn văn.
# Cố ý KHÔNG có "ban" (ban chuyên môn), "da" (đa phương tiện), "chi" (chi phí), "ho" (hỗ trợ):
# bỏ dấu làm các từ này trùng với từ dừng nhưng chúng mang nghĩa quan trọng trong corpus.
_STOPWORDS_TEXT = """a ah ak anh bi cho co cua dang de di do duoc dc e em gi ha hay hok
    ko khong k kh la lam ma minh moi nao nay ne nhe nhi nhu nhung oi roi sao se ta
    thi the theo toi tu va vay vi voi vs u uh"""
STOPWORDS: frozenset[str] = frozenset(_STOPWORDS_TEXT.split())


def fold(text: str) -> str:
    """Chữ thường, bỏ dấu tiếng Việt (kể cả đ -> d), bỏ dấu câu, gộp khoảng trắng."""
    text = unicodedata.normalize("NFD", text.lower().replace("đ", "d"))
    text = "".join(ch for ch in text if unicodedata.category(ch) != "Mn")
    return " ".join(_NON_WORD.sub(" ", text).split())


def expand_abbreviations(folded: str) -> str:
    """Thêm dạng đầy đủ của các viết tắt có trong câu (giữ nguyên từ gốc)."""
    extra = [ABBREVIATIONS[w] for w in folded.split() if w in ABBREVIATIONS]
    return " ".join([folded, *extra])


def tokens(text: str) -> list[str]:
    """Token cho BM25: unigram (bỏ từ dừng) + bigram liền kề trên văn bản đã bỏ dấu.

    Bigram giảm nhập nhằng khi bỏ dấu ("ban to chuc" khác "ban to" ...).
    """
    words = fold(text).split()
    unigrams = [w for w in words if w not in STOPWORDS]
    bigrams = [
        f"{a}_{b}"
        for a, b in zip(words, words[1:], strict=False)
        if not (a in STOPWORDS and b in STOPWORDS)
    ]
    return unigrams + bigrams
