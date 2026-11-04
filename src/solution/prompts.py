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

ANSWER_USER = """TÀI LIỆU:
{context}

CÂU HỎI: {query}{rewritten}"""


def format_context(docs: list[Document]) -> str:
    return "\n\n".join(f"[{i}] ({d.club} | {d.topic})\n{d.text}" for i, d in enumerate(docs, 1))


def answer_messages(query: str, rewritten: str, docs: list[Document], style: str) -> list[dict]:
    if style == "baseline":
        context = "\n\n".join(d.text for d in docs)
        return [{"role": "user", "content": BASELINE_USER.format(context=context, query=query)}]
    hint = f"\n(Diễn giải câu hỏi: {rewritten})" if rewritten and rewritten != query else ""
    return [
        {"role": "system", "content": ANSWER_SYSTEM},
        {
            "role": "user",
            "content": ANSWER_USER.format(
                context=format_context(docs), query=query, rewritten=hint
            ),
        },
    ]
