# Quy trình Git

Quy trình này phục vụ tiêu chí Technical ("quản lý mã nguồn với Git"): lịch sử commit đọc được như nhật ký
kỹ thuật, mỗi cải tiến có PR kèm số liệu, và bản nộp Private Test truy ngược được tới đúng commit.

## 1. Nhánh

| Nhánh | Dùng cho | Ví dụ |
|---|---|---|
| `main` | Luôn chạy được, đã qua CI. Chỉ cập nhật qua PR | |
| `feat/<tên>` | Tính năng mới của pipeline hoặc chatbot (tên: tiếng Việt không dấu, gạch ngang) | `feat/e1-truy-xuat-hybrid`, `feat/giao-dien-chatbot` |
| `exp/<tên>` | Thực nghiệm có thể bị bỏ; merge khi có số liệu tốt hơn | `exp/rerank-cross-encoder` |
| `fix/<tên>` | Sửa lỗi | `fix/loi-doc-json` |
| `docs/<tên>` | Chỉ thay đổi tài liệu | `docs/slide-pitching` |

Mỗi nhánh một mục tiêu. Thực nghiệm thất bại vẫn nên ghi lại trong `docs/experiments.md` (kết quả âm cũng là dữ liệu cho pitching).

## 2. Commit: Conventional Commits

```
<type>(<scope>): <mô tả ngắn bằng tiếng Việt có dấu>

<thân bằng tiếng Việt: vì sao thay đổi, số liệu nếu có>
```

- `type` và `scope` viết tiếng Anh theo chuẩn; **mô tả và thân viết tiếng Việt**.
- **Không thêm dòng co-author hay attribution của công cụ AI** (`Co-Authored-By`, "Generated with ...").

| type | Khi nào |
|---|---|
| `feat` | Thêm khả năng mới (bước pipeline, tính năng chatbot) |
| `fix` | Sửa lỗi |
| `perf` | Tăng điểm/tốc độ mà không thêm tính năng (chỉnh trọng số, prompt) |
| `refactor` | Đổi cấu trúc, không đổi hành vi |
| `test` | Thêm/sửa test |
| `docs` | Tài liệu, sổ thực nghiệm |
| `build` / `ci` | Đóng gói, phụ thuộc, GitHub Actions |
| `chore` | Việc vặt (gitignore, cấu hình editor) |

Scope gợi ý: `retrieval`, `query`, `generation`, `pipeline`, `bench`, `app`, `eval`.

Ví dụ: `perf(retrieval): giảm trọng số dense cho câu gốc không dấu (0.5 → 0.2), +1.8 Retrieval train`.

## 3. Pull Request

1. Tạo nhánh từ `main` mới nhất: `git switch main && git pull && git switch -c feat/<tên>`.
2. Commit nhỏ, mỗi commit một thay đổi logic.
3. Trước khi push: `ruff check . && ruff format --check . && pytest`.
4. `git push -u origin feat/<tên>` rồi `gh pr create`. Điền mẫu PR (`.github/pull_request_template.md`), **luôn có bảng số liệu trước/sau**.
5. CI xanh → merge bằng **"Create a merge commit"** để giữ nguyên các commit chi tiết trong lịch sử.
6. Xóa nhánh sau khi merge.

## 4. Tag các mốc

| Tag | Ý nghĩa |
|---|---|
| `e<N>` | Commit sinh ra một lần nộp Public quan trọng, ví dụ `e1` |
| `private-test` | Bản code chốt trước 08/11. **Ngày 08/11 chỉ checkout tag này và chạy**, không sửa code (quy định mục 2) |

```bash
git tag -a e1 -m "E1: hybrid retrieval + query rewrite + prompt v2"
git push origin e1
```

## 5. Không bao giờ commit

- `.env` (key cá nhân). Nếu lỡ commit: báo BTC thu hồi key ngay, xóa commit là chưa đủ.
- `outputs/` (predictions: không chia sẻ giữa thí sinh), `.cache/`, `.venv/`.
- Thư mục công cụ cá nhân (`.claude/`, cấu hình editor) và ghi chú cá nhân (`STUDY_REPORT.md`).

Không dùng `git push --force` lên `main`.
