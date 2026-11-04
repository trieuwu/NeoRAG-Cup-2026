# Chiến lược và danh sách phương án

Tài liệu định hướng để tối đa điểm theo 4 tiêu chí: Benchmark 40%, Pitching 25%, Technical 20%, Demo 15%.
Mỗi phương án ghi: ý tưởng, metric nhắm tới, chi phí ngân sách, độ khó, trạng thái. Số liệu thực tế ghi ở
[experiments.md](experiments.md).

Trạng thái: ✅ đã làm · 🔜 nên làm tiếp · 🧪 thử nếu còn thời gian · ⛔ không nên

## 0. Kiến trúc (E1, xem `docs/experiments.md` cho E2–E6)

```
câu hỏi
  │
  ├─► QueryRewriter (Haiku, 1 lời gọi): thêm dấu, mở rộng viết tắt, nhận diện CLB, tách câu hỏi con
  │
  ├─► HybridRetriever
  │     ├─ BM25 trên văn bản bỏ dấu (unigram + bigram), câu hỏi = gốc + viết tắt mở rộng + bản viết lại
  │     ├─ Dense bge-m3: bản viết lại (w=1), câu gốc (w=0.2), từng câu hỏi con (w=0.7)
  │     ├─ Gộp bằng Reciprocal Rank Fusion (k=60)
  │     └─ Cộng điểm cho đoạn thuộc đúng CLB được hỏi
  │
  └─► Generator (Haiku, 1 lời gọi): top-5 đoạn kèm [CLB | chủ đề], prompt v2 trả lời ngắn, bám tài liệu, từ chối đúng cách
```

E6: anchors (doc2query) thêm một danh sách BM25 vào RRF; Dynamic Few-Shot thay few-shot tĩnh; prompt v6.
Public: 52.40 (baseline) → 80.09 (E3) → 82.28 (E4) → 83.55 (E5).

Retrieval train E1: 72.2 (baseline) → 85.7. String Presence 71.8 → 84.7. ROUGE-L 42.0 → 57.4.

## 1. Benchmark: Retrieval (50% điểm Benchmark)

| # | Phương án | Nhắm tới | Chi phí | Độ khó | Trạng thái |
|---|---|---|---|---|---|
| R1 | Viết lại câu hỏi bằng Haiku (thêm dấu, mở rộng viết tắt) | câu không dấu/viết tắt | 1 lời gọi/câu | thấp | ✅ |
| R2 | Hybrid BM25 bỏ dấu + dense, gộp RRF | mọi loại | 0 | thấp | ✅ |
| R3 | Ưu tiên đoạn thuộc CLB được hỏi | nhầm CLB | 0 | thấp | ✅ (tác dụng nhỏ, +0.5) |
| R4 | **Rerank bằng cross-encoder local** (`BAAI/bge-reranker-v2-m3`) trên top-20 | MRR, NDCG | 0 (chạy máy, cần `install.py --local`) | trung bình | ⛔ máy chỉ có CPU: chậm, thiếu RAM; đã viết code, tắt mặc định |
| R5 | **Doc2query**: Haiku sinh 5–8 câu hỏi mẫu cho mỗi đoạn (một lần, 118 lời gọi), index thêm vào BM25/dense | diễn đạt khác, không dấu | ~118 lời gọi một lần | trung bình | ✅ E6 (Synthetic Question Anchors, BM25): Retrieval +3.2 |
| R6 | Rerank bằng Haiku (listwise top-15 → xếp lại) | MRR, NDCG | +1 lời gọi/câu | trung bình | 🧪 (so với R4) |
| R7 | Câu hỏi con: xen kẽ kết quả từng câu hỏi con thay vì chỉ cộng RRF, để đảm bảo mỗi ý có doc trong top-5 | nhiều đoạn, so sánh | 0 | thấp | ✅ E4 (rewrite v2/v3 tách câu hỏi con theo từng CLB): +2.0 |
| R8 | HyDE: Haiku viết câu trả lời giả định rồi embed | diễn đạt khác | +1 lời gọi/câu | thấp | 🧪 |
| R9 | Tinh chỉnh trọng số RRF, depth, rrf_k bằng `python -m solution bench` | tổng | 0 | thấp | 🔜 (cẩn thận overfit train) |
| R10 | Mở rộng từ điển viết tắt/đồng nghĩa (ví dụ "lên clb" → "sinh hoạt") | không dấu | 0 | thấp | 🧪 |
| R11 | Mở rộng tập ứng viên rerank (pool 30, chọn tối đa 10, anchors chỉ thêm ứng viên) | Recall@5 | +token rerank | thấp | ⛔ E8: stress +0.2/+0.4 (cần +1); pool 20 đã chứa 98% đoạn đúng |

Lưu ý: metric tính tại k=5 nhưng nộp đủ 10 id không bị phạt (Precision không vào điểm). Thứ tự top-5 là quan trọng nhất.

## 2. Benchmark: Generation (50% điểm Benchmark)

| # | Phương án | Nhắm tới | Chi phí | Độ khó | Trạng thái |
|---|---|---|---|---|---|
| G1 | Prompt v2: ngắn, chép nguyên số liệu, không chào hỏi, câu từ chối chuẩn | ROUGE-L, SP, Noise | 0 | thấp | ✅ |
| G2 | **Few-shot** 3–4 cặp hỏi-đáp từ train (đúng văn phong đáp án chuẩn ~200 ký tự) | ROUGE-L, Relevancy | +token/câu | thấp | ✅ E3 tĩnh, E6 động (Dynamic Few-Shot, Leave-One-Out) |
| G3 | **Lọc ngữ cảnh**: chỉ đưa đoạn có điểm rerank vượt ngưỡng (2–5 đoạn thay vì cố định 5) | Noise, Groundedness | 0 | trung bình (cần R4) | 🔜 |
| G4 | Hậu xử lý: bỏ markdown, bỏ câu dẫn dắt, cắt độ dài | ROUGE-L | 0 | thấp | 🧪 |
| G5 | Tự kiểm (Haiku đọc lại câu trả lời + tài liệu, xóa câu không có căn cứ) | Groundedness, Noise | +1 lời gọi/câu | trung bình | 🧪 |
| G6 | Phân tích `per_query.jsonl` sau mỗi lần chấm judge: tìm câu Noise cao, sửa prompt theo nhóm | tổng | 0 | thấp | ✅ E5 (chẩn đoán Relevancy, Query Rewriter) |
| G7 | Trả lời theo từng câu hỏi con rồi gộp | so sánh, nhiều đoạn | +lời gọi | cao | ⛔ (đắt, dài dòng) |
| G8 | Prompt v7 theo khuôn câu đáp án chuẩn ("Theo ...", `;`, nêu phần có khi thiếu dữ liệu) và/hoặc few-shot động style-only | ROUGE-L, SP | 0 | thấp | ⛔ E9 (nhánh `perf/van-phong-tra-loi`): ROUGE +2.1, SP +3.6 nhưng Groundedness −2, Abstention/Relevancy giảm với v7; tổng train ±0.6 → giữ E7 |

Cấm: chèn chỉ dẫn hay nhãn chấm vào câu trả lời nhằm tác động judge.

## 3. Quy trình đo và nộp bài

- Vòng lặp nhanh: `python -m solution bench` (retrieval, gần như miễn phí) → `python -m solution warm train` →
  `neorag run train --no-judge --pipeline solution.pipeline:SolutionPipeline`.
- Chấm judge đầy đủ chỉ ở các mốc (mỗi lần tốn vài phần ngân sách 5 USD). Kiểm tra số dư trước.
- Public Test: tối đa 10 lượt/ngày. Nộp sau mỗi cải tiến lớn; train và Public có thể lệch (đề Public khó hơn).
- **Chọn bản cho Private** dựa trên cả train lẫn Public, không chọn bản chỉ tốt nhờ một lần nộp may mắn (judge lệch ±1).
- 07/11: tag `private-test`, chạy thử end-to-end trên `public_test` từ tag đó.

## 4. Demo Product (15%)

| # | Phương án | Trạng thái |
|---|---|---|
| D1 | Chatbot hiển thị nguồn trích dẫn (CLB, chủ đề, đoạn văn) cho mỗi câu trả lời | 🔜 |
| D2 | Hiển thị câu hỏi đã được hiểu (bản viết lại) và latency | 🔜 |
| D3 | Streaming câu trả lời (giảm thời gian chờ cảm nhận) | 🔜 |
| D4 | Hội thoại nhiều lượt: viết lại câu hỏi kèm lịch sử ("thế còn MPC thì sao?") | 🧪 |
| D5 | Câu hỏi gợi ý, lọc theo CLB, giao diện riêng (Streamlit có theme hoặc FastAPI + React) | 🧪 |
| D6 | Cache câu trả lời + chạy sẵn index khi khởi động để demo mượt | 🔜 |

## 5. Technical (20%)

| # | Hạng mục | Trạng thái |
|---|---|---|
| T1 | Code thí sinh tách riêng `src/solution/`, cấu hình qua dataclass + biến môi trường | ✅ |
| T2 | Unit test offline cho từng thành phần, CI GitHub Actions (ruff + pytest) | ✅ |
| T3 | Conventional Commits, nhánh theo tính năng, PR có bảng số liệu, tag mốc | ✅ ([git-workflow.md](git-workflow.md)) |
| T4 | README của repo: kiến trúc, cách chạy pipeline và chatbot, kết quả | 🔜 |
| T5 | Sổ thực nghiệm có commit SHA cho từng kết quả | ✅ |
| T6 | Sơ đồ kiến trúc (cho README và slide) | 🔜 |

## 6. Pitching (25%)

Câu chuyện đề xuất (20 phút):
1. Bài toán và cách chấm (1 phút).
2. Baseline và phân tích lỗi: câu không dấu/viết tắt chỉ Recall@5 0.44, câu trả lời dài gấp đôi đáp án (3 phút).
3. Từng quyết định kỹ thuật, mỗi quyết định kèm số liệu ablation từ `python -m solution bench` (6 phút).
4. Kết quả train / Public / Private, chi phí trên mỗi câu hỏi (3 phút).
5. Demo chatbot với câu khó: không dấu, so sánh 2 CLB, câu không có đáp án (5 phút).
6. Hạn chế và hướng phát triển (2 phút).

Chuẩn bị hỏi đáp: vì sao RRF thay vì cộng điểm; vì sao bỏ dấu cho BM25; chi phí/độ trễ của bước viết lại câu hỏi;
cách tránh overfit train; xử lý câu không có đáp án; vì sao không chunking.

## 7. Lịch đề xuất

**Cập nhật 04/11:** Giai đoạn A (E8, E9) không tìm được cải tiến vượt tiêu chí → chốt E7 cho Private. Tiếp theo:
Giai đoạn B (đóng băng cấu hình, script chạy một lệnh, chống lỗi, diễn tập) rồi Giai đoạn C (README, kiến trúc, API chatbot).

| Ngày | Việc |
|---|---|
| 04/11 | E1 (xong), nộp Public lần đầu. Bắt đầu R4 rerank |
| 05/11 | R4/R5, G2/G3; chấm judge một mốc; nộp Public |
| 06/11 | Chatbot D1–D3, D6; README T4 |
| 07/11 | Chốt bản tốt nhất, tag `private-test`, nộp Public cuối, kiểm tra ngân sách |
| 08/11 | Chỉ chạy `neorag run private_test` từ tag và nộp |
| Sau | Slide + luyện demo |
