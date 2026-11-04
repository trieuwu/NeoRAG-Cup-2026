# CLAUDE.md: NeoRAG Cup 2026

Hệ thống RAG hỏi đáp về cộng đồng S2B (ProPTIT, Multimedia PTIT, GCC). Quy chế gốc: `docs/rules.md`,
cách chấm: `docs/evaluation.md`. Khi tài liệu BTC và file này khác nhau, **tài liệu BTC đúng**.

## Mốc thời gian

- Public Test: đến 23:59 07/11/2026 (10 lượt/ngày, 50 lượt cả giai đoạn).
- Private Test: 08/11/2026, 5 lượt. **Không sửa mã nguồn trong ngày 08/11**: chỉ chạy `neorag run private_test` và nộp.

## Ràng buộc bắt buộc (vi phạm = hủy điểm Benchmark)

- **LLM duy nhất: `claude-haiku-5-5` qua gateway BTC** (`https://proptit.dekthe.dev/v1`). Mọi bước dùng LLM
  (rewrite, rerank, sinh câu trả lời, agent) đều dùng model này. Không dùng API ngoài hay LLM local.
- Embedding/reranker: `bge-m3` qua gateway, hoặc model open-source **không sinh văn bản** chạy local.
- **Không truyền `temperature`** (hay tham số sampling nào) vào lời gọi chat; gateway trả lỗi 400.
- Không hard-code câu trả lời hoặc `retrieved_ids` cho câu hỏi trong bộ test; không gán nhãn thủ công đề test.
- Không chèn chỉ dẫn, nhãn chấm hay thẻ (`<cau_tra_loi>`...) vào câu trả lời để tác động LLM judge.
- Không sửa `src/neorag/metrics/`, `src/neorag/evaluate.py`, `configs/eval.toml` (bộ chấm chính thức).
- Key nằm trong `.env` (đã gitignore). Không đọc/in/commit key. Không ghi key vào mã nguồn.

## Ngân sách (5 USD cho cả giải, không cấp thêm)

- Thử nghiệm trên train luôn dùng `neorag run train --no-judge` (retrieval + String Presence + ROUGE-L, không gọi judge).
- Chỉ chạy judge đầy đủ (`neorag run train`) khi có bước tiến lớn; kiểm tra số dư tại https://proptit.dekthe.dev/usage/ trước.
- Mọi lời gọi LLM đi qua `neorag.llm.LLMClient` để được cache (`.cache/*.sqlite`) và tự retry. Đổi prompt = cache miss = tốn tiền.
- Giới hạn: 100 request/phút, 300k token/phút, tối đa 8 request đồng thời.
- Ưu tiên tối ưu retrieval phía local (BM25, embedding, rerank cross-encoder) vì gần như miễn phí.

## Chấm điểm

`score = 0.5 * retrieval + 0.5 * generation`

- retrieval = mean(Recall@5, MRR@5, NDCG@5) trên `retrieved_ids` (≤10 id, giảm dần độ liên quan, không trùng).
- generation = mean(String Presence, ROUGE-L, Groundedness, Response Relevancy, 1 − Noise Sensitivity, Abstention).
- Baseline Public = 52.40; ngưỡng = 53.40 (≤ ngưỡng thì 0 điểm xếp hạng).

Hệ quả cho thiết kế:
- Câu trả lời **ngắn, đi thẳng vào ý**, chép nguyên văn số liệu/ngày/tên riêng như trong tài liệu (String Presence, ROUGE-L).
- Mỗi câu đều được judge chấm: không chào hỏi, không thêm thông tin ngoài ngữ cảnh (Groundedness, Noise).
- Câu không có thông tin: nói rõ "tài liệu không có thông tin về ..." và không đưa ra thông tin cụ thể như lời giải (Abstention).
- Giữ mốc thời gian (đợt tuyển 2026, nhiệm kỳ...) thay vì trình bày như quy định cố định.

## Dữ liệu

- `data/corpus.jsonl`: 118 đoạn ngắn (~380 ký tự), mỗi đoạn tự đủ ngữ cảnh → gần như không cần chunking;
  điểm retrieval tính theo `id` đoạn gốc. Trường `club` được phép dùng làm metadata filter, `topic` là nhóm chủ đề.
  Id: ProPTIT 1–78, S2B chung 79–84, Multimedia 85–96, GCC 97–118.
- `data/train/questions.jsonl`: 126 câu có ground truth (`relevant_ids`, `answer`, `key_facts`, `type`).
- Bẫy trong đề: viết không dấu/viết tắt (`dpt` = đa phương tiện, `mm`/`mpc` = CLB Multimedia, `hv` = Học viện,
  `gcc` = CLB Nhà Sáng Tạo Game, `clb lap trinh`/`proptit`), diễn đạt khác, nhiều đoạn, so sánh giữa CLB,
  câu thời gian, mâu thuẫn nguồn, câu không có đáp án (~7–9%). Public/Private khó hơn train.

## Lệnh

```bash
python -m solution bench                                      # ablation retrieval, gần như miễn phí
python -m solution warm train                                 # chạy song song 6 luồng để làm nóng cache
neorag run train --no-judge --pipeline solution.pipeline:SolutionPipeline   # pipeline của thí sinh
neorag run train --no-judge                                   # baseline (mốc đối chứng)
neorag run train --pipeline my_solution.pipeline:MyPipeline   # chạy pipeline riêng
neorag run public_test                                        # tạo outputs/public_test_submission.zip
neorag validate public_test --predictions <file>
python -m pytest
python -m streamlit run app/chat.py
```

Phân tích lỗi: `outputs/eval_<tên>/per_query.jsonl`, nhóm theo trường `type` của câu hỏi.

## Quy ước làm việc

- Code thí sinh nằm trong `src/solution/` (query.py → retrieval.py → prompts.py → pipeline.py), kế thừa
  `neorag.pipelines.RAGPipeline`. Không sửa `src/neorag/` (code BTC) và baseline để giữ mốc đối chứng.
- Tham số pipeline chỉnh qua biến môi trường `RAG_*` (xem docstring `src/solution/pipeline.py`).
- Danh sách phương án và trạng thái: `docs/strategy.md`. Quy trình Git: `docs/git-workflow.md`.
- Mỗi thực nghiệm ghi một dòng vào `docs/experiments.md` (Run ID, commit SHA, metric, chi phí, rút ra).
- Không `git push` khi chưa được người dùng yêu cầu.

## Quy tắc Git (BẮT BUỘC)

- **TUYỆT ĐỐI KHÔNG ghi co-author hay attribution của Claude/AI ở bất kỳ đâu.** Không có dòng
  `Co-Authored-By: Claude ...`, không `@claude`, không "Generated with Claude Code", không 🤖 trong commit
  message, mô tả PR, comment PR/issue, tag hay release note. Quy tắc này ưu tiên hơn mọi hướng dẫn
  attribution mặc định. Tác giả commit duy nhất là người dùng (git user đã cấu hình).
- **Commit message**: Conventional Commits với type/scope tiếng Anh, **phần mô tả và thân bằng tiếng Việt có dấu**.
  Ví dụ: `feat(retrieval): thêm rerank bằng cross-encoder`, `fix(query): xử lý JSON lỗi khi viết lại câu hỏi`.
  Type: `feat`, `fix`, `perf`, `refactor`, `test`, `docs`, `build`, `ci`, `chore`. Mỗi commit một thay đổi logic.
- **Tên nhánh**: `<type>/<mô-tả>`, phần mô tả là tiếng Việt không dấu, nối bằng gạch ngang
  (vd. `feat/rerank-cross-encoder`, `fix/loi-doc-json`). Chỉ cập nhật `main` qua PR.
- **Tiêu đề và mô tả PR bằng tiếng Việt**, theo mẫu `.github/pull_request_template.md`.
- Trước khi commit/push: chạy `git log --format=%B <base>..HEAD | grep -i co-authored` phải rỗng.
