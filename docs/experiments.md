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
| E0 | `9916ad6` | **Baseline BTC.** R: dense `bge-m3`, embed nguyên đoạn, cosine top-10. G: 1 lời gọi `claude-haiku-5-5`, top-5 đoạn, prompt tối giản | 78.21 | 69.25 | 69.10 | **73.61** (Retrieval 72.19 · Generation 75.04) | 52.40 | — | Số Public lấy từ log mẫu của BTC (Retrieval 42.31, Generation 62.48; R@5 43.45, MRR@5 44.21, NDCG@5 39.29). Ngưỡng xếp hạng 53.40. Retrieval train 72 nhưng Public chỉ 42: đề Public khó hơn nhiều |
| E1 | `fefa875` | **Hybrid + rewrite + prompt v2.** R: Haiku viết lại câu hỏi (thêm dấu, mở rộng viết tắt, nhận diện CLB, tách câu hỏi con) → BM25 bỏ dấu + dense bge-m3, gộp RRF, ưu tiên đúng CLB. G: prompt v2 (ngắn, chép nguyên số liệu, từ chối chuẩn), top-5 đoạn kèm [CLB \| chủ đề] | 91.33 | 83.57 | 82.11 | (nj) Retrieval **85.67** · SP 84.71 · ROUGE-L 57.36 | — | — | Retrieval +13.5, SP +12.9, ROUGE-L +15.4 so với E0. 2 lời gọi Haiku/câu. Chưa chấm judge, chưa nộp Public |
| E2/E3 | `95b085d` | **+ đa dạng hóa CLB + few-shot.** R: như E1, thêm đa dạng hóa theo CLB (câu hỏi nhiều CLB → mỗi CLB ≥ 1 đoạn top-5); cross-encoder có trong code nhưng tắt (chưa đo xong). G: prompt v3 = v2 + 4 ví dụ few-shot từ train | 92.01 | 83.77 | 82.55 | (nj) Retrieval **86.11** · SP 87.32 · ROUGE-L 60.35 | **80.09** | — | Retrieval +0.4, SP +2.6, ROUGE-L +3.0 so với E1 trên train. **Public: Retrieval 82.19 (R@5 81.79 · MRR@5 87.18 · NDCG@5 77.61), Generation 77.98 (SP 85.04 · ROUGE-L 52.96 · Groundedness 92.31 · Relevancy 57.25 · 1−Noise 80.34 · Abstention 100).** +27.7 so với baseline Public, top 7 bảng xếp hạng. Điểm yếu nhất: ROUGE-L, Relevancy; câu trả lời Public trung vị 274 ký tự (đáp án chuẩn ~200) |

### Public E2/E3: so với baseline

| Metric | Baseline (E0) | E2/E3 | Chênh lệch |
|---|---:|---:|---:|
| Recall@5 | 43.45 | 81.79 | +38.3 |
| MRR@5 | 44.21 | 87.18 | +43.0 |
| NDCG@5 | 39.29 | 77.61 | +38.3 |
| **Retrieval** | 42.31 | **82.19** | **+39.9** |
| String Presence | 52.14 | 85.04 | +32.9 |
| ROUGE-L | 33.11 | 52.96 | +19.9 |
| Groundedness | 83.29 | 92.31 | +9.0 |
| Response Relevancy | 60.07 | 57.25 | **−2.8** |
| 1 − Noise | 46.26 | 80.34 | +34.1 |
| Abstention | 100 | 100 | 0 |
| **Generation** | 62.48 | **77.98** | +15.5 |
| **Raw score** | 52.40 | **80.09** | **+27.7** |

Rút ra: Response Relevancy là metric duy nhất **giảm** so với baseline. Câu hỏi Public phần lớn viết không dấu/văn nói,
còn câu hỏi judge sinh ngược từ câu trả lời là tiếng Việt chuẩn có dấu → cosine thấp; câu trả lời dài hoặc kèm ý phụ
(số điện thoại cũ, so sánh chi tiết từng CLB) cũng kéo Relevancy và ROUGE-L xuống.

### Ablation retrieval E2 (`python -m solution bench`, train, 122 câu)

| Cấu hình | Recall@5 | MRR@5 | NDCG@5 | Retrieval |
|---|---:|---:|---:|---:|
| full E1 | 91.33 | 83.57 | 82.11 | 85.67 |
| full E1, **không** ghép metadata vào đoạn | 88.59 | 80.68 | 79.01 | 82.76 |
| **full + đa dạng hóa CLB (mặc định E2)** | **92.01** | **83.77** | **82.55** | **86.11** |
| full + cross-encoder rerank | chưa đo | | | |

Rút ra:
- **Ghép "CLB | chủ đề" vào đoạn khi index đáng giá +2.9**: giữ.
- Đa dạng hóa CLB: +0.4 (tác dụng ở câu so sánh nhiều CLB).
- Cross-encoder `BAAI/bge-reranker-v2-m3` chưa có số liệu: lần chạy bench bị dừng vì máy thiếu RAM
  (torch không thấy GPU trong môi trường chạy nên chạy CPU). Điểm đã tính được cache trong `.cache/rerank.sqlite`.
- 18/122 câu E1 còn đoạn đúng ngoài top-5, chủ yếu là câu **nhiều đoạn / so sánh** (vd. "CLB nào lâu đời nhất và
  trẻ nhất?" cần đoạn giới thiệu của cả 3 CLB). Đây là chỗ reranker và đa dạng hóa nhắm tới.

### Ablation retrieval E1 (`python -m solution bench`, train, 122 câu có doc đúng)

Mỗi dòng bỏ hoặc chỉ giữ một thành phần so với `full`. Đo trên commit `fefa875`.

| Cấu hình | Recall@5 | MRR@5 | NDCG@5 | Retrieval |
|---|---:|---:|---:|---:|
| dense only, không rewrite (≈ baseline) | 76.50 | 68.16 | 68.09 | 70.91 |
| BM25 only, không rewrite | 80.40 | 76.97 | 72.97 | 76.78 |
| hybrid, không rewrite | 86.27 | 78.52 | 77.08 | 80.63 |
| dense only + rewrite | 82.86 | 76.15 | 75.06 | 78.02 |
| BM25 only + rewrite | 85.45 | 78.92 | 76.64 | 80.34 |
| full, không club boost | 89.14 | 81.23 | 79.67 | 83.35 |
| full (w_dense_original = 0.5) | 89.28 | 82.05 | 80.24 | 83.85 |
| **full (w_dense_original = 0.2, mặc định E1)** | **91.33** | **83.57** | **82.11** | **85.67** |

Rút ra:
- **BM25 trên văn bản bỏ dấu một mình đã hơn dense** (+5.9): câu hỏi không dấu khớp từ khóa tốt hơn embedding.
- **Hybrid > từng thành phần** (+3.9 so với BM25): hai tín hiệu bổ sung cho nhau.
- **Rewrite đóng góp +3 trên hybrid**; với dense riêng là +7.1.
- **Club boost tác dụng nhỏ** (+0.5); boost 0.5–3 cho kết quả gần như nhau.
- Giảm trọng số dense cho câu gốc không dấu 0.5 → 0.2: +1.8. Các giá trị 0–0.3 chênh nhau ≤ 1 câu (nhiễu); chọn 0.2 để không overfit.
- Nhóm không dấu/viết tắt: Recall@5 0.44 → 0.85.

## Ghi chú phân tích lỗi

Ghi các phát hiện từ `per_query.jsonl` theo nhóm `type` câu hỏi (không dấu/viết tắt, so sánh, nhiều đoạn, không có đáp án...).

### E0, baseline trên train

Generation đầy đủ (có judge): String Presence 71.81 · ROUGE-L 41.97 · Groundedness 94.26 · Response Relevancy 68.28 ·
Noise Sensitivity 26.07 (→ 1−Noise 73.93) · Abstention 100 (11/11) · BLEU-4 26.02 (không tính điểm).
Chấm judge 126 câu mất 5m20s.

So với Public (baseline): Groundedness và Abstention đã cao ở cả hai tập; chênh lệch lớn nằm ở retrieval
(72 → 42) và Noise (26 → 54), tức là truy xuất sai doc kéo theo câu trả lời sai.

| Loại câu hỏi | n | Recall@5 | MRR@5 | ROUGE-L | String Presence |
|---|---:|---:|---:|---:|---:|
| không dấu/viết tắt | 26 | **0.44** | **0.36** | 0.36 | **0.46** |
| diễn đạt khác | 22 | 0.86 | 0.73 | 0.41 | 0.77 |
| nhiều đoạn | 20 | 0.81 | 0.71 | 0.41 | 0.80 |
| so sánh | 20 | 0.79 | 0.78 | 0.39 | 0.79 |
| thời gian | 12 | 1.00 | 0.86 | 0.47 | 0.92 |
| không có đáp án | 11 | 0.93 | 0.76 | – | – |
| trực tiếp | 8 | 1.00 | 1.00 | 0.63 | 0.73 |
| thiếu dữ liệu | 5 | 0.90 | 0.70 | 0.47 | 0.60 |
| mâu thuẫn nguồn | 2 | 1.00 | 1.00 | 0.46 | 1.00 |

- **Điểm nghẽn lớn nhất: câu không dấu/viết tắt** (Recall@5 0.44 so với ~0.85 ở các nhóm khác). `bge-m3` embed câu
  không dấu kém. Đề Public có tỷ lệ loại câu này rất cao, nên Retrieval Public chỉ còn 42. Hướng xử lý: Haiku
  khôi phục dấu và mở rộng viết tắt trước khi truy xuất, cộng BM25 trên văn bản đã bỏ dấu.
- **Câu trả lời quá dài**: trung vị 428 ký tự, so với 196 ở đáp án chuẩn → ROUGE-L thấp (0.42). Hướng xử lý: prompt
  yêu cầu trả lời ngắn, chép nguyên số liệu/tên riêng.
- Latency trung vị 3.7 s/câu (chạy tuần tự).
