"""Prompt sinh câu trả lời.

Thiết kế bám theo bộ chấm (docs/evaluation.md):
- ROUGE-L, Response Relevancy: trả lời ngắn, đi thẳng vào ý.
- String Presence: chép nguyên văn số liệu, ngày tháng, tên riêng.
- Groundedness, Noise Sensitivity: mỗi câu đều bị chấm -> không chào hỏi, không thêm ý ngoài tài liệu.
- Abstention: câu không có trong tài liệu -> nói rõ không có thông tin, không đoán.
"""

from __future__ import annotations

from neorag.data import Document

# Prompt gốc của baseline, giữ lại để làm đối chứng khi chạy ablation.
BASELINE_USER = """Dựa vào các tài liệu dưới đây, hãy trả lời câu hỏi.

TÀI LIỆU:
{context}

CÂU HỎI: {query}"""

ANSWER_SYSTEM = """Bạn là trợ lý hỏi đáp về cộng đồng S2B tại PTIT (CLB Lập Trình PTIT, CLB Multimedia PTIT, CLB Nhà Sáng Tạo Game PTIT).

Quy tắc trả lời:
1. Chỉ dùng thông tin trong TÀI LIỆU. Không dùng hiểu biết bên ngoài, không suy đoán.
2. Trả lời ngắn gọn, đi thẳng vào ý: thường 1-3 câu. Trả lời đủ mọi ý được hỏi, không thêm ý không được hỏi.
3. Không chào hỏi, không mở đầu kiểu "Dựa vào tài liệu", không kết thúc bằng lời mời hỏi thêm.
4. Giữ nguyên văn tên riêng, số liệu, ngày tháng, tên sự kiện như trong tài liệu.
5. Thông tin gắn với một thời điểm (đợt tuyển, nhiệm kỳ, năm) thì nêu rõ mốc thời gian đó.
6. Nếu các tài liệu ghi khác nhau, nêu cả hai kèm nguồn hoặc thời điểm của từng thông tin.
7. Nếu TÀI LIỆU không có thông tin để trả lời, trả lời đúng một câu: "Tài liệu hiện có không có thông tin về <nội dung được hỏi>." và không đưa ra con số, tên hay quy định nào khác như câu trả lời.
8. Nếu chỉ trả lời được một phần, trả lời phần có thông tin và nói rõ phần nào tài liệu không đề cập.
9. Viết văn xuôi tiếng Việt có dấu, không dùng markdown (không in đậm, không tiêu đề). Chỉ liệt kê bằng gạch đầu dòng khi có từ 4 mục trở lên."""

# v4: siết độ dài (ROUGE-L), câu đầu nhắc lại chủ thể của câu hỏi (Response Relevancy),
# cho phép đối chiếu từ đồng nghĩa khi đọc tài liệu nhưng trả lời bằng đúng từ của tài liệu (String Presence).
ANSWER_SYSTEM_V4 = """Bạn là trợ lý hỏi đáp về cộng đồng S2B tại PTIT (CLB Lập Trình PTIT, CLB Multimedia PTIT, CLB Nhà Sáng Tạo Game PTIT).

Quy tắc trả lời:
1. Chỉ dùng thông tin trong TÀI LIỆU. Không dùng hiểu biết bên ngoài.
2. Trả lời trong 1-2 câu (tối đa 3 câu nếu câu hỏi có từ 3 ý trở lên). Chỉ nêu đúng thông tin được hỏi; không thêm thông tin phụ như số liên hệ cũ, nguồn, thông tin về CLB hoặc đợt không được hỏi.
3. Câu đầu tiên trả lời thẳng vào câu hỏi và nhắc lại chủ thể của câu hỏi bằng tên đầy đủ (ví dụ "CLB Multimedia PTIT có ...", "Vòng Training của CLB Lập Trình PTIT kéo dài ..."). Câu hỏi có/không thì bắt đầu bằng "Có." hoặc "Không.".
4. Khi đối chiếu câu hỏi với tài liệu, coi các cách diễn đạt tương đương là cùng nghĩa (ví dụ "phòng riêng để chụp ảnh, quay phim" ~ "studio riêng"; "ra đời", "lập ra" ~ "thành lập"; "anh chị khóa trước" ~ "thành viên cũ"). Khi viết câu trả lời, dùng đúng từ ngữ của tài liệu.
5. Giữ nguyên văn tên riêng, số liệu, ngày tháng, tên sự kiện như trong tài liệu. Thông tin gắn với một thời điểm (đợt tuyển, nhiệm kỳ, năm) thì nêu mốc thời gian đó.
6. Chỉ khi các tài liệu mâu thuẫn trực tiếp về đúng điều được hỏi, nêu ngắn gọn cả hai kèm thời điểm.
7. Nếu TÀI LIỆU không có thông tin để trả lời, trả lời đúng một câu: "Tài liệu hiện có không có thông tin về <nội dung được hỏi>." và không đưa ra con số, tên hay quy định nào khác.
8. Nếu chỉ trả lời được một phần, trả lời phần có thông tin rồi nói ngắn gọn phần nào tài liệu không đề cập.
9. Không chào hỏi, không mở đầu kiểu "Dựa vào tài liệu", không markdown, không gạch đầu dòng."""

ANSWER_USER = """TÀI LIỆU:
{context}

CÂU HỎI: {query}{rewritten}"""


# Few-shot (prompt "v3"): 4 cặp hỏi-đáp lấy nguyên văn từ tập train (được phép theo quy định mục 1),
# chọn theo 4 kiểu câu: trực tiếp, so sánh, nhiều đoạn, không có đáp án. Chỉ dạy văn phong và độ dài
# của đáp án chuẩn (~120-200 ký tự), không kèm tài liệu để tiết kiệm token.
FEW_SHOT: list[tuple[str, str]] = [
    (  # train-0001, trực tiếp
        "CLB Lập Trình PTIT được thành lập ngày nào và phương châm hoạt động là gì?",
        'CLB Lập Trình PTIT (PROPTIT) được thành lập ngày 09/10/2011, với phương châm hoạt động "Chia sẻ để cùng nhau phát triển".',
    ),
    (  # train-0017, so sánh
        "Trong 3 CLB thuộc S2B, CLB nào lâu đời nhất và CLB nào trẻ nhất?",
        "CLB Lập Trình PTIT lâu đời nhất (thành lập ngày 09/10/2011), tiếp theo là CLB Multimedia PTIT (thành lập ngày 10/11/2012). CLB Nhà Sáng Tạo Game PTIT (GCC) trẻ nhất, ra đời năm 2023.",
    ),
    (  # train-0038, nhiều đoạn
        "Đợt tuyển 2023 của GCC, phải qua những vòng nào thì mới được đi First Meeting?",
        "Đợt tuyển năm 2023 của CLB Nhà Sáng Tạo Game PTIT (GCC) gồm vòng CV, vòng Phỏng vấn và vòng Training. First Meeting GCC 2023 dành cho các bạn đã vượt qua vòng CV và vòng Phỏng vấn để vào vòng Training.",
    ),
    (  # train-0103, không có đáp án
        "Cộng đồng S2B có fanpage hay website riêng không, địa chỉ là gì?",
        "Tài liệu không có thông tin về fanpage hay website riêng của cộng đồng S2B; tài liệu chỉ có kênh liên hệ riêng của từng CLB thành viên.",
    ),
]

FEW_SHOT_INTRO = (
    "Các ví dụ dưới đây chỉ minh họa VĂN PHONG và ĐỘ DÀI câu trả lời mong muốn. "
    "Với câu hỏi thật, chỉ dùng thông tin trong TÀI LIỆU được cung cấp."
)


def few_shot_messages() -> list[dict]:
    msgs: list[dict] = []
    for i, (q, a) in enumerate(FEW_SHOT):
        prefix = FEW_SHOT_INTRO + "\n\n" if i == 0 else ""
        msgs += [
            {"role": "user", "content": f"{prefix}CÂU HỎI (ví dụ): {q}"},
            {"role": "assistant", "content": a},
        ]
    return msgs


def format_context(docs: list[Document]) -> str:
    return "\n\n".join(f"[{i}] ({d.club} | {d.topic})\n{d.text}" for i, d in enumerate(docs, 1))


def answer_messages(query: str, rewritten: str, docs: list[Document], style: str) -> list[dict]:
    if style == "baseline":
        context = "\n\n".join(d.text for d in docs)
        return [{"role": "user", "content": BASELINE_USER.format(context=context, query=query)}]
    hint = f"\n(Diễn giải câu hỏi: {rewritten})" if rewritten and rewritten != query else ""
    shots = few_shot_messages() if style in {"v3", "v4"} else []
    system = ANSWER_SYSTEM_V4 if style == "v4" else ANSWER_SYSTEM
    return [
        {"role": "system", "content": system},
        *shots,
        {
            "role": "user",
            "content": ANSWER_USER.format(
                context=format_context(docs), query=query, rewritten=hint
            ),
        },
    ]
