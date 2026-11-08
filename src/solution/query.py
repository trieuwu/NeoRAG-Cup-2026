"""Hiểu câu hỏi bằng claude-haiku-5-5: thêm dấu, mở rộng viết tắt, nhận diện CLB, tách ý.

Một lời gọi LLM cho mỗi câu hỏi, kết quả được cache bởi LLMClient. Nếu LLM trả về JSON lỗi,
pipeline vẫn chạy tiếp với câu hỏi gốc (không bao giờ làm hỏng cả lượt chạy).
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field

from neorag.llm import LLMClient
from solution.resilience import record

# Khóa CLB chuẩn -> giá trị trường `club` trong data/corpus.jsonl
CLUBS: dict[str, str] = {
    "proptit": "CLB Lập Trình PTIT",
    "multimedia": "CLB Multimedia PTIT",
    "gcc": "CLB Nhà Sáng Tạo Game PTIT (GCC)",
    "s2b": "Cộng đồng S2B",
}

REWRITE_SYSTEM_V1 = """Bạn chuẩn hóa câu hỏi của sinh viên gửi tới chatbot của cộng đồng S2B tại Học viện Công nghệ Bưu chính Viễn thông (PTIT).
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

# v2: câu hỏi nhiều CLB thì tách một câu hỏi con cho TỪNG CLB (ghi rõ tên CLB), để truy xuất được
# đoạn văn của từng CLB thay vì đoạn tổng quan chung của S2B.
REWRITE_SYSTEM_V2 = REWRITE_SYSTEM_V1.replace(
    """3. "sub_queries": nếu câu hỏi gồm nhiều ý hoặc so sánh nhiều CLB, tách thành các câu hỏi con có dấu, mỗi câu một ý (tối đa 3). Câu hỏi một ý thì để [].
""",
    """3. "sub_queries": nếu câu hỏi gồm nhiều ý, tách thành các câu hỏi con có dấu, mỗi câu một ý (tối đa 3). Câu hỏi một ý thì để [].
   Nếu câu hỏi so sánh hoặc hỏi về nhiều CLB (kể cả "các CLB trong S2B"), viết MỘT câu hỏi con cho TỪNG CLB, ghi rõ tên đầy đủ của CLB và diễn đạt bằng thông tin cụ thể cần tìm (ví dụ "CLB Lập Trình PTIT được thành lập khi nào?" thay vì "CLB nào lâu đời nhất?"), và liệt kê tất cả các CLB đó trong "clubs".
""",
)
assert REWRITE_SYSTEM_V2 != REWRITE_SYSTEM_V1

# v3 (E5): từ điển PTIT, luật phân giải chữ không dấu đa nghĩa theo ngữ cảnh, không gắn CLB cho câu hỏi
# cấp Học viện, và chỉ tách câu hỏi con theo CLB khi thật sự SO SÁNH (không áp dụng cho câu xin tư vấn).
REWRITE_SYSTEM_V3 = """Bạn chuẩn hóa câu hỏi của sinh viên gửi tới chatbot của cộng đồng S2B tại Học viện Công nghệ Bưu chính Viễn thông (PTIT).
S2B gồm 3 CLB:
- proptit: CLB Lập Trình PTIT (PROPTIT, ProPTIT, "clb lập trình", "clb lt", "pro").
- multimedia: CLB Multimedia PTIT (MPC, "mm", "multi", CLB Sáng tạo Đa phương tiện; hợp với sinh viên ngành Đa phương tiện - "dpt", "pt": thiết kế, vẽ, chụp ảnh, quay dựng, truyền thông).
- gcc: CLB Nhà Sáng Tạo Game PTIT (GCC, Game Creators Club, "clb game", "clb làm game").
- s2b: cộng đồng chung của cả 3 CLB (sự kiện chung, sinh nhật chung, quan hệ giữa các CLB).

Từ viết tắt:
- Chung: hv = Học viện, sv = sinh viên, tv = thành viên, tvm = thành viên mới, nk = nhiệm kỳ, bcn = ban chủ nhiệm, cn = chủ nhiệm, ko/k/kh = không, dc/đc = được, e = em, sn = sinh nhật, hd/hđ = hoạt động, ib = nhắn tin (inbox), onl = online, off = offline, ntn = như thế nào, j = gì.
- Ban: btt / ban tt = ban truyền thông, bsk = ban sự kiện, bđn/bdn = ban đối ngoại, cm = chuyên môn, nd = nội dung, ban tc / tcns = ban tài chính nhân sự, bđh/bdh = ban điều hành.
- Tuyển thành viên: ttv = tuyển thành viên, tnm = thu nạp mới, pv = phỏng vấn, cv = hồ sơ CV, gen = thế hệ (khóa tuyển), biggame/bg = sự kiện BigGame.
- Học thuật: cvht = cố vấn học tập, attt = an toàn thông tin, cntt = công nghệ thông tin, đtvt/vtvt = điện tử viễn thông, oop = lập trình hướng đối tượng, cđr = chuẩn đầu ra, đkmh = đăng ký môn học, tc/tín = tín chỉ, đrl = điểm rèn luyện, cpp = C++.
- Địa điểm: cs = cơ sở, cs hđ = cơ sở Hà Đông, cs nt = cơ sở Ngọc Trục, ttth = trung tâm thực hành; gsa, gsb, a2, a3 là tên nhà/phòng, giữ nguyên.

Chữ không dấu nhiều nghĩa: chọn nghĩa theo các từ xung quanh.
- "ve": đi với "quay", "chụp", "thiết kế", "tay", "hình" -> "vẽ"; đi với "hỏi", "biết", "nói", "thông tin" -> "về".
- "nhan": đi với "tin", "ib", "hỏi", "page", "fanpage" -> "nhắn"; đi với "được", "thưởng", "quà", "đồ", "giải" -> "nhận".
- "thi": đi với "cuối khóa", "giữa kỳ", "môn", "kiểm tra", hoặc "thi gì", "có thi không" -> "thi" (kiểm tra, cuộc thi); đứng nối hai vế câu, trước "nên", "vào", "phải", "có" -> "thì".
- "dung lop" trong ngữ cảnh CLB -> "đứng lớp": người giảng dạy, người chủ trì buổi học (KHÔNG phải học viên).
- "ban" trước tên ban (sự kiện, truyền thông, đối ngoại, chuyên môn...) -> "Ban"; "ban" + "đột xuất" / "việc" -> "bận".

Nhiệm vụ (KHÔNG trả lời câu hỏi):
1. "query": viết lại câu hỏi thành tiếng Việt có dấu đầy đủ, rõ ràng, mở rộng mọi viết tắt. Giữ nguyên mọi ý được hỏi và vai trò của người hỏi, không thêm ý mới. Chỉ ghi tên CLB khi câu hỏi nhắc tới CLB đó.
2. "clubs": khóa các CLB mà câu hỏi nhắc tới, chọn trong ["proptit", "multimedia", "gcc", "s2b"]. Câu hỏi về cấp Học viện mà không nhắc CLB nào thì để []. Không tự gắn CLB mà người hỏi không nhắc tới.
3. "sub_queries": nếu câu hỏi gồm nhiều ý hoặc cần liên kết nhiều mốc thông tin, tách thành các câu hỏi con độc lập (tối đa 3):
  - Câu hỏi so sánh giữa các CLB: viết MỘT câu hỏi con cho TỪNG CLB cụ thể.
  - Câu hỏi liên kết 2 sự kiện/mốc thời gian/đối tượng (ví dụ: "đội thi giải X có ai làm chủ nhiệm không", "nhiệm kỳ mới nhất so với nhiệm kỳ trước", "sự kiện A đến sự kiện B cách nhau bao lâu"): BẮT BUỘC tách thành 2 câu hỏi con riêng biệt để tìm độc lập từng đối tượng (ví dụ câu 1: "Thành viên đội tuyển thi giải X gồm những ai?", câu 2: "Danh sách chủ nhiệm CLB qua các nhiệm kỳ?").
  - Câu hỏi một ý đơn giản thì để [].

Chỉ trả về một object JSON đúng dạng sau, không giải thích:
{"query": "...", "clubs": ["..."], "sub_queries": ["..."]}"""

REWRITE_PROMPTS = {"v1": REWRITE_SYSTEM_V1, "v2": REWRITE_SYSTEM_V2, "v3": REWRITE_SYSTEM_V3}

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
    if isinstance(rewritten, str) and rewritten.strip():
        rewritten = rewritten.strip()
    else:
        record("rewrite", "JSON hỏng hoặc thiếu trường query: dùng câu hỏi gốc")
        rewritten = original
    clubs = [c for c in data.get("clubs") or [] if isinstance(c, str) and c in CLUBS]
    subs = [s.strip() for s in data.get("sub_queries") or [] if isinstance(s, str) and s.strip()]
    return QueryPlan(original, rewritten, list(dict.fromkeys(clubs)), subs[:3])


class QueryRewriter:
    def __init__(self, llm: LLMClient, model: str, prompt: str = "v1"):
        self.llm, self.model = llm, model
        self.system = REWRITE_PROMPTS[prompt]

    def __call__(self, query: str) -> QueryPlan:
        reply = self.llm.chat(
            [
                {"role": "system", "content": self.system},
                {"role": "user", "content": query},
            ],
            model=self.model,
        )
        return parse_plan(query, reply)
