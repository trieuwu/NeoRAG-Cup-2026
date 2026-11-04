## Mục tiêu

<!-- Thay đổi này giải quyết vấn đề gì? Dựa trên phân tích lỗi nào (loại câu hỏi, metric yếu)? -->

## Thay đổi

-

## Kết quả thực nghiệm

<!-- Lấy từ `python -m solution bench` và/hoặc `neorag run train [--no-judge]`. Ghi thêm vào docs/experiments.md. -->

| Run | Recall@5 | MRR@5 | NDCG@5 | Retrieval | String Presence | ROUGE-L | Score Train | Public |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Trước |  |  |  |  |  |  |  |  |
| Sau |  |  |  |  |  |  |  |  |

Chi phí ước tính: <!-- $ theo trang usage -->

## Checklist

- [ ] Chỉ dùng `claude-haiku-5-5` qua gateway BTC; không truyền `temperature`
- [ ] Không hard-code câu trả lời / `retrieved_ids` của bộ test
- [ ] Không sửa bộ chấm (`src/neorag/metrics/`, `src/neorag/evaluate.py`, `configs/eval.toml`)
- [ ] Không commit `.env`, `outputs/`, `.cache/`
- [ ] `ruff check .` và `pytest` đều qua
- [ ] Đã cập nhật `docs/experiments.md`
