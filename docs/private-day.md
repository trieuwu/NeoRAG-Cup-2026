# Kịch bản ngày Private Test (08/11/2026)

Nguyên tắc: **không sửa mã nguồn** (quy chế), chỉ chạy bản đã gắn tag `private-final` bằng một lệnh. Mọi lỗi lúc chạy
được xử lý bằng cách **chạy lại**, không bằng cách sửa code.

| Hạng mục | Giá trị |
|---|---|
| Bản chạy | tag `private-final` = commit `cf4c184` = E7 (Public 88.95) + chống lỗi + script một lệnh |
| Cấu hình | `configs/private.env` (giá trị E7 ghi tường minh, không chứa key) |
| Thời gian thi | 00:00 – 23:59 08/11, 42 câu, tối đa 5 lượt nộp, **lượt nộp CUỐI được tính**, xem được điểm của mình |
| Thời gian chạy (diễn tập 05/11, cache rỗng) | **~6 phút** cho 42 câu (latency median 8.0s, p95 12.9s), cài môi trường từ đầu ~2.5 phút |
| Chi phí một lần chạy (diễn tập, đếm token thật) | **~$0.075** (126 lời gọi Haiku, 475k token vào, 51k token ra) + embedding bge-m3 |

## 1. Trước ngày thi (07/11)

- [ ] `git fetch --tags && git checkout private-final`; `git describe --tags` in ra `private-final`.
- [ ] Có file `.env` (key gateway). Không mở, không in key.
- [ ] Số dư tại https://proptit.dekthe.dev/usage/ ≥ $1.3 (đủ 3 lần chạy với biên rất rộng; một lần ~$0.075).
- [ ] Diễn tập lại một lần nếu máy đổi môi trường:
  `powershell -ExecutionPolicy Bypass -File scripts\run_private.ps1 -Split public_test` → phải in `SẴN SÀNG NỘP`.

## 2. Sáng 08/11 (chạy sớm, ví dụ 07:00)

1. Tải `data/private_test/questions.jsonl` từ repository của BTC, đặt đúng đường dẫn đó (file đã được gitignore nên
   working tree vẫn sạch). Kiểm tra có 42 dòng.
2. Chạy:

   ```powershell
   git checkout private-final
   powershell -ExecutionPolicy Bypass -File scripts\run_private.ps1
   ```

   (Linux/macOS/Git Bash: `bash scripts/run_private.sh`.) Script tự kiểm tra tag, working tree sạch, file câu hỏi,
   có `.env`; nạp `configs/private.env`; chạy; validate; sanity check; xuất `outputs/private_<HHMM>.zip` (không ghi đè).
3. Đọc dòng cuối:
   - `SẴN SÀNG NỘP: outputs/private_HHMM.zip` → nộp file đó (mục 4).
   - `CÓ CẢNH BÁO ĐỎ` hoặc `LỖI` → xử lý theo mục 3, **chưa nộp**.
4. Sao lưu ngay `.cache/solution.sqlite`, `outputs/private_HHMM_pred.jsonl`, `outputs/private_HHMM_log.jsonl`.
   BTC có thể yêu cầu chạy lại để đối chiếu: Haiku cho kết quả khác nhau giữa các lần chạy KHÔNG có cache (diễn tập:
   chỉ 18/42 câu trùng tập top-5), nên cache và log là bằng chứng bài nộp đúng là output của pipeline. Chạy lại với
   cache này cho kết quả trùng 100%.

## 3. Khi có lỗi

| Dấu hiệu | Việc làm |
|---|---|
| `LỖI: HEAD ... không phải tag` | `git checkout private-final` rồi chạy lại |
| `LỖI: working tree có thay đổi` | `git stash` (không sửa code), chạy lại |
| `LỖI: không thấy data/private_test/questions.jsonl` | tải lại file câu hỏi của BTC |
| Đỏ: `N câu dùng fallback` (gateway 429/timeout/5xx) | đợi 5–10 phút rồi **chạy lại cùng lệnh**: câu đã ổn lấy từ cache (không đổi, không tốn tiền), chỉ câu lỗi được gọi lại vì kết quả fallback không được cache |
| Fallback vẫn còn sau 3 lần chạy (gateway sập lâu) | file vẫn hợp lệ (câu lỗi dùng thứ hạng local + trích đoạn); thử lại sau 1–2 giờ; chỉ nộp file có fallback nếu đã gần hết ngày và chưa có file xanh nào |
| Đỏ: tỷ lệ từ chối / độ dài lệch xa | mở `outputs/private_HHMM_log.jsonl` xem `incidents`; không sửa code; nếu không có sự cố nào thì đề Private khác đề Public, vẫn nộp |
| `neorag run thất bại` (mất mạng giữa chừng) | chạy lại script: cache giữ các câu đã xong |
| Hết số dư | không chạy thêm; nộp file xanh gần nhất |

**Không** chạy nhiều lần không cache rồi chọn bản có điểm cao: mỗi lần chạy lại dùng cache nên ra cùng một file; xóa
cache để "quay số" là chọn theo điểm Private và làm mất khả năng đối chiếu.

## 4. Nộp bài

- Lượt 1: file `SẴN SÀNG NỘP` đầu tiên. Ghi ngay vào bảng dưới.
- Giữ **≥ 2 lượt dự phòng** cho tình huống nộp lỗi (bài Failed không tính lượt) hoặc phải chạy lại.
- **Lượt nộp CUỐI được tính**: không bao giờ nộp một file kém hơn sau file tốt. Nếu đã nộp nhầm, nộp lại file tốt.
- Không nộp file có cảnh báo đỏ khi đã có file xanh.

| Lượt | Giờ | File | sha256 (12 ký tự, script in ra) | Điểm | Ghi chú |
|---|---|---|---|---|---|
| 1 | | | | | |
| 2 | | | | | |
| 3 | | | | | |
| 4 | | | | | |
| 5 | | | | | |

## 5. Sau khi nộp

- Ghi điểm Private vào `docs/experiments.md` (dòng E7, cột Private) vào ngày 09/11 trở đi.
- Không push code mới lên `main` trong ngày 08/11 (tag `private-final` đã cố định bản chạy).
