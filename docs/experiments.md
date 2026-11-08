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
| E4 | `f0f96b3` | **Rewrite v2 + prompt v4.** R: Haiku tách câu hỏi con cho TỪNG CLB khi câu hỏi nhiều CLB; đa dạng hóa viết lại (ưu tiên đoạn "Giới thiệu chung" có trong code nhưng tắt). G: prompt v4 = trả lời 1-2 câu, câu đầu nhắc chủ thể câu hỏi, đối chiếu từ đồng nghĩa nhưng trả lời bằng từ của tài liệu, + few-shot | 94.33 | 85.23 | 84.81 | (nj) Retrieval **88.12** · SP **88.81** · ROUGE-L **63.73** · tập con 42 câu có judge: **87.77** | **82.28** | — | Retrieval +2.0, SP +1.5, ROUGE-L +3.4 so với E3 trên train. **Public: Retrieval 82.68 (R@5 82.58 · MRR@5 86.71 · NDCG@5 78.75), Generation 81.89 (SP 83.97 · ROUGE-L 60.87 · Groundedness 96.15 · Relevancy 60.15 · 1−Noise 90.17 · Abstention 100).** So với E3 Public: ROUGE-L +7.9, 1−Noise +9.8, Relevancy +2.9, Retrieval +0.5 |
| E5 | `381fd46` | **Rewrite v3 + prompt v5.** R: từ điển viết tắt PTIT cho BM25 (có khớp cụm), rewrite v3 phân giải chữ không dấu theo ngữ cảnh (vẽ/về, nhắn/nhận, thi/thì, đứng lớp), không gắn CLB cho câu cấp Học viện, chỉ tách theo CLB khi thật sự so sánh. G: prompt v5 = v4 + không viết câu "tài liệu không có thông tin" cho điều không được hỏi, mỗi câu trả lời trực tiếp một ý, dùng tên gọi của người hỏi | 93.51 | 85.61 | 84.84 | (nj) Retrieval 87.99 · SP **89.32** · ROUGE-L **64.23** · tập con 42 câu có judge: **89.03** | **83.55** | — | **Public: Retrieval 83.67 (R@5 85.44 · MRR@5 85.52 · NDCG@5 80.05), Generation 83.43 (SP 88.46 · ROUGE-L 57.58 · Groundedness 97.44 · Relevancy 60.55 · 1−Noise 96.58 · Abstention 100), hạng 7.** Tập con có judge so với E4: +1.26 (Relevancy 63.87 → 64.70, Groundedness 91.25 → 97.50, Noise 10.0 → 5.0, ROUGE-L 65.27 → 66.13, SP 89.50 → 90.75). Retrieval train −0.13 (ngang, 4 câu tốt lên / 4 câu kém đi do diễn đạt). File nộp: `outputs/public_test_submission.zip` (E4 giữ ở `public_test_submission_e4_82.28.zip`) |
| E6 | `4cec9a4` | **Paradigm shift: anchors + Dynamic Few-Shot + prompt v6.** R: Synthetic Question Anchors (Haiku sinh 8 câu hỏi giả định + thực thể cho mỗi đoạn, chỉ từ corpus), thêm danh sách BM25 trên anchors (w=1.5) vào RRF. G: 4 ví dụ (câu hỏi, đáp án chuẩn) của train giống câu hỏi nhất (BM25 + dense, Leave-One-Out) thay few-shot tĩnh; prompt v6: câu đầu chứa đủ chủ thể và khía cạnh được hỏi, không lấy thông tin từ ví dụ | **95.15** | **89.96** | **88.51** | (nj) Retrieval **91.21** · SP **90.30** · ROUGE-L **65.86** · tập con 42 câu có judge: **91.20** | **82.84** ⚠️ | — | **Public THẤP hơn E5 (83.55 → 82.84): Retrieval 83.67 → 82.87 (R@5 85.44 = · MRR@5 85.52 → 84.13 · NDCG@5 80.05 → 79.06), Generation 83.43 → 82.80 (SP 88.46 → 84.62 · ROUGE-L 57.58 → 59.04 · Relevancy 60.55 → 60.38 · 1−Noise 96.58 → 95.30). Mức tăng trên train không chuyển sang Public; 5/42 câu trả lời Public có > 30% 4-gram trùng đáp án ví dụ few-shot.** So với E5 trên train: Retrieval train +3.2 (NDCG@5 +3.7), tập con có judge +2.17 (Relevancy 64.70 → 66.81, SP 90.75 → 93.58, Groundedness 97.50 → 98.75). Nhóm không dấu MRR@5 0.76 → 0.89. File nộp: `outputs/public_test_submission.zip` (E5 giữ ở `public_test_submission_e5_83.55.zip`) |
| E7 | `cbbb5d7` | **E5 + rerank listwise bằng Haiku.** R: như E5 (không anchors), thêm 1 lời gọi Haiku/câu: đọc câu hỏi (kèm câu hỏi con) và top-20 ứng viên RRF, trả về danh sách id xếp hạng; gộp RRF lần hai với w_rerank = 4; đoạn không được chọn giữ thứ hạng RRF. G: như E5 (prompt v5, few-shot tĩnh) | 97.68 | **100.00** | **98.11** | (nj) Retrieval **98.59** · SP 88.67 · ROUGE-L 64.41 · tập con 42 câu có judge: **93.32** | **88.95** | — | **Public: Retrieval 93.80 (R@5 91.59 · MRR@5 97.62 · NDCG@5 92.20), Generation 84.09 (SP 88.46 · ROUGE-L 58.50 · Groundedness 100 · Relevancy 60.17 · 1−Noise 97.44 · Abstention 100). +5.40 so với E5: Retrieval +10.1, generation +0.7.** Bench Retrieval: E5 87.99 → w_rerank 1: 95.81 · 2: 97.99 · 4: 98.80 · 10: 98.85 (trước khi sửa lỗi thứ tự id), 98.59 sau khi sửa. Tập con có judge: SP 94.50, ROUGE-L 67.31, Groundedness 100, Relevancy 65.95, 1−Noise 98.75. Không dùng thông tin train trong prompt reranker → ít rủi ro overfit hơn anchors. Chi phí: +1 lời gọi Haiku/câu, latency +vài giây |

### E8 (nhánh `perf/mo-rong-ung-vien-rerank`, commit `cf589bb`): mở rộng tập ứng viên rerank, TRƯỢT vòng 1

Ý tưởng: pool rerank 20 → 30, Haiku chọn tối đa 10 đoạn (thay vì 8), anchors chỉ bổ sung ứng viên (top-5 BM25
trên anchors), không cộng vào RRF. Đo bằng `python -m solution bench [--stress]`. Bộ stress = 122 câu train bỏ dấu
hoàn toàn và thay viết tắt (dpt, mm/mpc, hv, gcc, clb lap trinh/proptit, tv, sv, ko, dc), sinh bằng luật
(`solution.stress`), không dùng câu Public/Private.

| | E7 (pool 20, max 8) | pool 30 / max 10 + anchors | pool 30 / max 8 + anchors |
|---|---:|---:|---:|
| Pool trung bình | 20.0 | 30.3 | 30.3 |
| **Train**: Recall của pool | 98.36 | 99.45 | 99.45 |
| Train: Recall pool, nhóm nhiều đoạn | 0.97 | 0.97 | 0.97 |
| Train: R@5 / MRR@5 / NDCG@5 | 97.68 / 100 / 98.11 | 98.63 / 100 / 98.72 | 98.22 / 100 / 98.35 |
| **Train: Retrieval** | 98.59 | 99.12 (+0.53) | 98.86 (+0.27) |
| **Stress**: Recall của pool | 98.09 | 99.32 | 99.32 |
| Stress: Recall pool, nhóm nhiều đoạn | 0.97 | 0.97 | 0.97 |
| Stress: R@5 / MRR@5 / NDCG@5 | 97.40 / 97.40 / 96.08 | 97.40 / 97.54 / 96.59 | 97.81 / 97.75 / 96.54 |
| **Stress: Retrieval** | 96.96 | 97.18 (+0.22) | 97.37 (+0.41) |

Tiêu chí giữ (đặt trước khi chạy): stress tăng ≥ 1 VÀ train không giảm quá 0.3. **Cả hai cấu hình trượt** → giữ E7,
không chạy vòng 2 (generation), không nộp Public. Chi phí ước tính ~850 lời gọi Haiku (~3.5M token vào, ~$0.35 theo
giá niêm yết). Rút ra:
- Pool 20 của E7 đã chứa 98% đoạn đúng ở cả train lẫn stress: nút thắt không nằm ở tập ứng viên.
- Bộ stress chỉ khó hơn train ~1.6 điểm: bước viết lại câu hỏi (rewrite v3) đã khôi phục dấu và viết tắt gần như
  trọn vẹn, nên mở rộng ứng viên không có đất để tăng. Anchors không thêm được đoạn đúng nào vào pool.
- Code (`RAG_RERANK_MAX`, `RAG_ANCHORS_CANDIDATES_ONLY`, `bench --stress`, cột Recall@pool) được giữ làm công cụ đo,
  mặc định vẫn là E7.

### E9 (nhánh `perf/van-phong-tra-loi`, không merge, chỉ lưu vết): cấu trúc Generation, TRƯỢT tiêu chí

**Chẩn đoán trước khi thử (miễn phí, train E7 `--no-judge`, 115 câu có đáp án):**
- Câu trả lời **không dài hơn** đáp án chuẩn: trung vị 184 so với 201 ký tự, 1.77 so với 1.71 câu. Trong 20 câu
  ROUGE-L thấp nhất có Recall@5 = 1: đáp án chuẩn 45.8 âm tiết, E7 38.6.
- Khác biệt ở khuôn câu: đáp án chuẩn mở đầu bằng nguồn/thời điểm ("Theo nội quy ...") 41.7% (E7 15.7%), nối mục
  bằng `;` 29.6% (E7 0.9%); E7 thêm tên gọi trong ngoặc "(ProPTIT)" 40% (chuẩn 2.6%). Không bên nào dùng gạch đầu dòng.
- Nhóm "thiếu dữ liệu" yếu nhất (ROUGE-L 0.47, SP 0.50): E7 chỉ từ chối, đáp án chuẩn nêu phần tài liệu có.
- Relevancy (tập con 42 câu E7 có judge): nhóm có dấu 0.746, nhóm không dấu/viết tắt 0.530 → nhóm có dấu đã gần
  trần paraphrase của bge-m3, phần thiếu chủ yếu do câu không dấu.

**Thử nghiệm** (cùng retrieval E7; dynamic few-shot = 4 ví dụ train gần nhất, Leave-One-Out, bỏ ví dụ có đoạn đúng
trùng các đoạn trong prompt):

| Train 126 câu | E7 (v5 + few-shot tĩnh) | G1: v7 | G2: v5 + dynamic | G3: v7 + dynamic |
|---|---:|---:|---:|---:|
| String Presence | 88.67 | 90.55 | **92.25** | 92.17 |
| ROUGE-L | 64.41 | 66.30 | 66.53 | **66.61** |
| Groundedness | 99.57 | – | 97.39 | 97.54 |
| Response Relevancy | 67.91 | – | **68.55** | 65.35 |
| 1 − Noise | 96.23 | – | 94.93 | 96.52 |
| Abstention | 100 | – | 100 | 90.91 |
| **Điểm train (judge)** | **92.36** | – | 92.60 | 91.72 |
| 4-gram trùng với ví dụ động (TB / số câu > 30%) | 8.7% / 4 | 7.4% / 2 | 9.4% / 3 | 8.0% / 2 |

Tiêu chí giữ (đặt trước): ROUGE-L +2.0, SP không giảm, Groundedness và Abstention không giảm quá 1.
- **G3 trượt**: Abstention −9.1 (train-0071: câu "Tài liệu chỉ ghi ... có Chủ nhiệm ..." bị coi là đưa thông tin như
  câu trả lời), Groundedness −2.0, Relevancy −2.6 (mở đầu "Theo Phòng truyền thống ..." làm câu hỏi sinh ngược lệch).
  Lỗi nằm ở prompt v7, không ở few-shot động.
- **G2 trượt** ở Groundedness (−2.2, 5 câu từ 1.0 xuống 0.5); tổng điểm train +0.24, trong mức nhiễu của judge.
- Không có dấu hiệu chép ví dụ (mức trùng 4-gram ngang E7, vốn không thấy ví dụ): bộ lọc "style-only" chặn được
  lỗi của E6.
- Kết luận: **giữ E7**. Prompt v7 (`RAG_PROMPT=v7`) chỉ có trên nhánh `perf/van-phong-tra-loi`, không merge vào `main` để bản Private không chứa code chết.

Chi phí ước tính: 3 biến thể `--no-judge` ~380 lời gọi (~$0.1); judge đủ 126 câu cho E7 (84 câu chưa có cache), G2,
G3 (~$0.5 theo giá niêm yết).

### E10 (nhánh `test/bo-do-hard-dev`): thước đo hard-dev sinh từ corpus, KHÔNG DÙNG ĐƯỢC → bỏ vòng lặp Pha 2

Mục tiêu: một bộ đo retrieval gần Public hơn train (khoảng hụt E7: train 98.59, Public 93.80) để chạy vòng lặp tăng
điểm có kiểm soát. Tiêu chí đặt trước: retrieval E7 trên hard-dev phải thấp hơn train ít nhất 3 điểm, nếu không thì
thước đo vô dụng.

Cách tạo (`python -m solution harddev`, `src/solution/harddev.py`): 130 nhóm 1-3 đoạn chọn bằng luật cố định
(so sánh 2 CLB cùng chủ đề, nhiều đoạn cùng CLB gần nhau theo bge-m3, câu có mốc thời gian), Haiku viết câu hỏi kiểu
sinh viên (một nửa không dấu/viết tắt), một lời gọi Haiku độc lập kiểm tra trên nhóm + 6 đoạn gây nhiễu gần nhất. Giữ
71/130 câu có tập đoạn cần trùng khớp nhóm gốc (loại 54 thừa/sai đoạn, 4 thiếu đoạn, 1 không viết được). Không dùng
câu Public/Private. File: `data/solution/hard_dev.jsonl`.

| E7 | Pool | R@pool | R@5 | MRR@5 | NDCG@5 | Retrieval |
|---|---:|---:|---:|---:|---:|---:|
| train (122 câu) | 20 | 98.36 | 97.68 | 100 | 98.11 | 98.59 |
| stress (122 câu) | 20 | 98.09 | 97.40 | 97.40 | 96.08 | 96.96 |
| **hard-dev (71 câu)** | 20 | 99.30 | 99.30 | 98.59 | 98.16 | **98.68** |

Theo loại (R@5 / NDCG@5): thời gian 1.00/0.99, nhiều đoạn 1.00/0.99, so sánh 0.97/0.95.

**Kết luận: hard-dev KHÔNG khó hơn train (98.68 so với 98.59) → thước đo vô dụng, bỏ vòng lặp Pha 2, giữ E7.**
Nguyên nhân: câu hỏi do Haiku viết từ chính các đoạn đúng và được Haiku kiểm tra lại, nên dùng đúng từ khóa/thực thể
của đoạn; reranker cũng là Haiku nên dễ nhận ra. Câu Public khó vì diễn đạt của người thật lệch khỏi từ ngữ tài liệu,
điều mà sinh tự động từ corpus không tái tạo được. Cả ba bộ đo nội bộ (train, stress, hard-dev) đều ở mức 97-99:
không còn tín hiệu nào để tối ưu retrieval mà không nhìn vào câu Public.

Chi phí (đếm token thật của request ra gateway, giá niêm yết Haiku): sinh + lọc 259 lời gọi, 469k token vào, 196k
token ra ≈ $0.145; bench E7 trên hard-dev 142 lời gọi ≈ $0.095. **Lũy kế Pha 2: ≈ $0.24** (ngân sách $1.2).

### Diễn tập Private (05/11, commit `cf4c184`): clone sạch, cài từ `requirements.lock.txt`

| Lần chạy | Cache | Thời gian | Kết quả |
|---|---|---|---|
| `neorag run public_test` (cấu hình `configs/private.env`) | rỗng | 352 s (median 8.0 s/câu, p95 12.9 s) | sanity xanh, 0 fallback; 126 lời gọi, 475k token vào, 51k ra ≈ **$0.073** |
| `scripts/run_private.ps1 -Split public_test` | cache của E7 | < 1 phút | **khớp 42/42** với file Public E7, sanity xanh |

Diễn tập lại trên commit `2d18a31` (thêm cache riêng mỗi lần chạy, PR #10), clone sạch: `-Cache` = cache E7 → khớp
42/42; mặc định cache mới → 5.3 phút, sanity xanh, 0 fallback, từ chối 19%, độ dài TB 222 ký tự.

**Độ dao động giữa các lần chạy không cache:** hai lần rút độc lập trùng tập top-5 với file E7 ở 18/42 và 19/42
câu, trùng nhau ở 22/42 câu. so với file E7 đã nộp, lần chạy cache rỗng chỉ trùng thứ tự top-5 ở
9/42 câu, trùng tập top-5 ở 18/42 câu, answer khác ở 41/42 câu. Haiku (không được đặt temperature) cho bản viết lại
câu hỏi và thứ hạng rerank khác nhau mỗi lần, nên điểm Public 88.95 là MỘT lần rút; điểm Private cũng sẽ là một lần
rút. Không có cách đo độ lệch này mà không nộp (không có đáp án Public); sanity check (từ chối 14%, độ dài 221 so với
223 ký tự) cho thấy hành vi tổng thể giữ nguyên.

### Ablation E6

**Bài học từ Public (82.84 < 83.55):** anchors không giúp retrieval Public (Recall@5 giữ nguyên, MRR/NDCG giảm nhẹ);
String Presence giảm 3.8 (deterministic, không phải nhiễu judge). Nghi vấn chính: Dynamic Few-Shot khiến câu trả lời
bắt chước/chép cụm từ của đáp án ví dụ thay vì giữ nguyên văn key facts của tài liệu; Leave-One-Out theo câu hỏi
không chặn được việc train có nhiều câu hỏi cùng một dữ kiện → điểm train/tập con lạc quan (đã cảnh báo trước).


**Retrieval** (`python -m solution bench`, train, 122 câu):

| Cấu hình | Recall@5 | MRR@5 | NDCG@5 | Retrieval |
|---|---:|---:|---:|---:|
| E5 | 93.51 | 85.61 | 84.84 | 87.99 |
| + anchors (BM25 + dense, w=1.0) | 90.92 | 86.97 | 83.63 | 87.17 |
| + anchors chỉ dense | 90.51 | 85.48 | 82.41 | 86.13 |
| + anchors chỉ BM25, w=0.5 / 1.0 / 2.0 / 3.0 | | | | 90.19 / 90.78 / 91.03 / 90.79 |
| **+ anchors chỉ BM25, w=1.5 (E6)** | **95.15** | **89.96** | **88.51** | **91.21** |
| E6 + anchors dense rewritten w=0.2 / 0.3 | | | | 91.02 / 90.71 |

Độ nhạy quanh E6 (đổi một tham số): w_bm25 0.5 → 90.18, 1.5 → 91.45; w_dense_rewritten 0.7 → 91.08, 1.5 → 91.24;
w_dense_original 0 → 91.05; rrf_k 30 → 91.55, 100 → 89.83; club_boost 0 → 91.00; tắt đa dạng hóa → 90.92.
Mọi thay đổi nhỏ nằm trong ±0.35 (≈ nhiễu một câu) nên **giữ nguyên** cấu hình, không chọn đỉnh nhỏ.

Rút ra: anchors giúp qua **BM25** (khớp từ khóa giữa câu hỏi và câu hỏi giả định, kể cả câu không dấu kiểu nhắn
tin), còn **dense trên anchors làm giảm điểm**: các câu hỏi giả định của nhiều đoạn giống nhau về ngữ nghĩa
("CLB ... thành lập khi nào?"), nên max-cosine kéo nhầm đoạn lên.

**Generation** (train 126 câu `--no-judge`, cùng retrieval E6):

| Cấu hình | String Presence | ROUGE-L |
|---|---:|---:|
| A: prompt v5 + few-shot tĩnh | 89.68 | 65.02 |
| B: prompt v5 + Dynamic Few-Shot | **90.57** | **65.94** |
| C: prompt v6 + Dynamic Few-Shot (E6) | 90.30 | 65.86 |

**Tập con 42 câu có judge:**

| | E4 | E5 | B | **C (E6)** |
|---|---:|---:|---:|---:|
| Retrieval | 92.22 | 92.38 | 95.66 | 95.66 |
| String Presence | 89.50 | 90.75 | 92.25 | **93.58** |
| ROUGE-L | 65.27 | 66.13 | **67.43** | 66.36 |
| Groundedness | 91.25 | 97.50 | 97.50 | **98.75** |
| Response Relevancy | 63.87 | 64.70 | 66.08 | **66.81** |
| 1 − Noise | 90.00 | 95.00 | **96.25** | 95.00 |
| **Điểm** | 87.77 | 89.03 | 91.12 | **91.20** |

Relevancy < 0.7: 22 câu (E5) → 20 câu (E6). Nhóm có dấu 0.738 → 0.763; nhóm không dấu 0.458 → 0.471 (giới hạn của
metric, xem chẩn đoán bên dưới). Các câu có dấu còn thấp chủ yếu vẫn kèm thông tin phụ không được hỏi.

Lưu ý: Dynamic Few-Shot trên train dùng Leave-One-Out theo câu hỏi, nhưng train có nhiều câu khác nhau hỏi cùng một
dữ kiện, nên ví dụ "gần" có thể chứa đúng đáp án → điểm train/tập con của B, C có thể lạc quan. Public sẽ kiểm chứng.

### Chẩn đoán Response Relevancy (tập con 42 câu train, có judge)

Relevancy = cosine bge-m3 giữa **câu hỏi gốc** và 3 câu hỏi judge sinh ngược từ câu trả lời.

| Nhóm | Relevancy chính thức | Nếu so với câu hỏi đã viết lại (có dấu) |
|---|---:|---:|
| không dấu/viết tắt (13 câu) | **0.442** | 0.809 |
| có dấu (27 câu) | 0.734 | 0.806 |

- Câu hỏi judge sinh ra **đúng trọng tâm** (~0.81 ở cả hai nhóm); điểm thấp chủ yếu do bge-m3 so câu gốc **không dấu**
  với câu hỏi có dấu. Đây là giới hạn của metric, mọi thí sinh đều gặp. Cách "ăn" phần chênh này là trả lời không
  dấu: làm sụp ROUGE-L/String Presence (bộ chuẩn hóa giữ dấu) và là thao túng judge → **không làm**.
- Phần sửa được: câu phụ không được hỏi kéo câu hỏi sinh ngược lệch hướng → prompt v5.

### Chẩn đoán Query Rewriter (E4, rewrite v2)

- Dịch **viết tắt** gần như hoàn hảo: 0 lỗi trong train (gcc 24/24, proptit 42/42, ko 10/10, mpc, mm, lt, nk, tv, cn, hv, dc...);
  15 viết tắt tự đặt ngoài train đúng 14/15.
- Lỗi thật là **chữ không dấu đa nghĩa**: "người dung lop" → "học viên" (đúng: đứng lớp, train-0066: SP 0, ROUGE-L 0.24),
  "nhan" → "nhận" (đúng: nhắn), "ve" → "thiết kế" (đúng: vẽ), "thi gì" → "có bài thi hay không".
- Tác dụng phụ của rewrite v2: câu xin tư vấn ("học dpt nên vào CLB nào") bị tách thành 3 câu hỏi con theo 3 CLB.
- Rewrite v3 sửa cả 11 ca thăm dò; train-0066: SP 0 → 1, ROUGE-L 0.24 → 0.85.

### Ablation E4 (train)

| Cấu hình retrieval (`python -m solution bench`) | Rewrite v1 | Rewrite v2 |
|---|---:|---:|
| không đa dạng hóa | 85.67 | **88.20** |
| đa dạng hóa (mặc định) | 86.11 | 88.12 |
| đa dạng hóa + ưu tiên đoạn "Giới thiệu chung" | 85.71 | 87.70 |

`w_dense_sub` 0.5 / 0.7 / 1.0 / 1.3 với rewrite v2: 88.27 / 88.12 / 88.24 / 88.15 (nhiễu, giữ 0.7).

| Prompt (tập con 42 câu train, cùng retrieval E4) | String Presence | ROUGE-L | Độ dài trung vị |
|---|---:|---:|---:|
| v3 | 90.00 | 62.04 | 212 |
| **v4** | 89.50 | **65.27** | 208 |

Rút ra:
- **Lỗi thật của câu so sánh nằm ở bước viết lại**, không ở bước đa dạng hóa: câu hỏi con chung chung ("CLB nào lâu
  đời nhất?") không khớp đoạn chứa "thành lập ngày ..."; tách theo từng CLB với thông tin cụ thể thì +2.1.
- Ép lấy đoạn "Giới thiệu chung" cho mọi câu nhiều CLB **làm giảm điểm** (−0.4): nhiều câu so sánh hỏi về tuyển
  thành viên, đào tạo... chứ không phải thông tin tổng quan. Giữ công tắc nhưng tắt.
- Chưa đo được Response Relevancy offline (cần judge); prompt v4 nhắm vào metric này qua quy tắc nhắc lại chủ thể.

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

### E11 (nhánh `perf/nhieu-y-day-du`, không merge): prompt v8 trên Private, KHÔNG TỐT HƠN bản chốt

Ngày 08/11 luật cho phép sửa mã. Thử prompt v8 = v5 + quy tắc "nêu đủ số liệu của từng đối tượng" (câu so sánh, nhiều CLB, nhiều mốc). Chỉ nộp Private, không đo trên train (ngân sách).

| Private (42 câu) | Bản chốt `62b84fd` (v5) | v8 |
|---|---:|---:|
| Retrieval | 96.78 | 96.87 |
| String Presence | 86.97 | **89.10** |
| ROUGE-L | 57.69 | 56.21 |
| Groundedness | 95.30 | 94.02 |
| Response Relevancy | 55.90 | 54.47 |
| 1 - Noise Sensitivity | 88.89 | 86.54 |
| Abstention | 100.00 | 100.00 |
| **Raw** | **88.79** | 88.46 |

- String Presence tăng +2.1 nhưng ROUGE-L, Groundedness, Relevancy, Noise đều giảm → câu trả lời đủ ý nhưng dài hơn.
- Chênh lệch tổng (−0.33) nằm trong biên dao động của judge (±1). Kết luận: giữ v5, v8 chỉ lưu vết ở nhánh riêng.
- Cảnh báo đỏ `private-0005` của `sanity_check` là báo động giả: Haiku trả `{"ranking": []}` (JSON hợp lệ, không đoạn nào liên quan vì corpus không có Gen 13 năm 2025), code coi danh sách rỗng là "JSON hỏng" và dùng thứ hạng RRF. Câu vẫn từ chối đúng.
