# Sổ tay thực nghiệm

Nhật ký A/B testing của pipeline. Mỗi thay đổi được đo so với dòng trước và so với baseline, để biết cải tiến nào
thực sự có tác dụng. Đây là nguồn số liệu cho phần trình bày kết quả ở buổi pitching.

## Quy ước

- **Run ID**: `E<số thứ tự>`, tăng dần, không tái sử dụng.
- **Commit SHA**: commit chứa đúng mã nguồn của lần chạy (`git rev-parse --short HEAD`), commit trước khi chạy.
- **Metric retrieval** (Recall@5, MRR@5, NDCG@5) và **Score Train**: lấy từ `outputs/eval_train_pred/report.json`
  của tập train, thang 0–100. Ghi `(nj)` nếu chạy `--no-judge` (Score Train khi đó chưa có phần judge, chỉ dùng để so tương đối).
- **Public Score**: raw score trên log chấm của aichallenge (thang 100), không phải điểm xếp hạng đã quy đổi.
- **Cost ($)**: chênh lệch số dư key trước/sau lần chạy, xem tại https://proptit.dekthe.dev/usage/.
- Chỉ thay đổi **một yếu tố** mỗi lần chạy để quy được kết quả cho đúng nguyên nhân.

## Bảng kết quả

| Run ID | Commit SHA | Mô tả phương pháp (Retrieval / Generation) | Recall@5 | MRR@5 | NDCG@5 | Score Train | Public Score | Cost ($) | Ghi chú rút ra |
|---|---|---|---:|---:|---:|---:|---:|---:|---|
| E0 | `9916ad6` | **Baseline BTC.** R: dense `bge-m3`, embed nguyên đoạn, cosine top-10. G: 1 lời gọi `claude-haiku-5-5`, top-5 đoạn, prompt tối giản | — | — | — | — | 52.40 | — | Số Public lấy từ log mẫu của BTC (Retrieval 42.31, Generation 62.48; R@5 43.45, MRR@5 44.21, NDCG@5 39.29). Ngưỡng xếp hạng 53.40. Điểm yếu nhất: retrieval, ROUGE-L 33.11, 1−Noise 46.26 |

## Ghi chú phân tích lỗi

Ghi các phát hiện từ `per_query.jsonl` theo nhóm `type` câu hỏi (không dấu/viết tắt, so sánh, nhiều đoạn, không có đáp án...).

- _(chưa có)_
