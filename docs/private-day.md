# Kịch bản ngày Private Test (08/11/2026)

Nguyên tắc: **không sửa mã nguồn** (quy chế), chỉ chạy bản đã gắn tag `private-final` bằng một lệnh. Mọi lỗi lúc chạy
được xử lý bằng cách **chạy lại**, không bằng cách sửa code.

| Hạng mục | Giá trị |
|---|---|
| Bản chạy | tag `private-final` (commit ghi trong mục 6) = E7 (Public 88.95) + chống lỗi + script một lệnh |
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

   (Linux/macOS/Git Bash: `bash scripts/run_private.sh`.) Script tự kiểm tra tag (HEAD phải đúng `private-final`),
   working tree sạch, file câu hỏi, có `.env`; nạp `configs/private.env`; tạo cache MỚI
   `outputs/private_runs/<HHMM>/cache.sqlite`; chạy; validate; sanity check; xuất `outputs/private_<HHMM>.zip`
   (không ghi đè) và sao lưu pred + log + zip + cache vào `outputs/private_runs/<HHMM>/`.
3. Đọc dòng cuối:
   - `SẴN SÀNG NỘP: outputs/private_HHMM.zip` → nộp file đó (mục 4).
   - `CÓ CẢNH BÁO ĐỎ` hoặc `LỖI` → xử lý theo mục 3, **chưa nộp**.
4. Script đã sao lưu lần chạy vào `outputs/private_runs/<HHMM>/`. Chép thêm cả thư mục `outputs/private_runs/` ra
   ngoài máy (USB/Drive). BTC có thể yêu cầu chạy lại để đối chiếu: Haiku cho kết quả khác nhau giữa các lần chạy
   KHÔNG có cache (diễn tập: chỉ 18/42 câu trùng tập top-5), nên cache và log của đúng lần chạy đã nộp là bằng chứng
   bài nộp là output của pipeline. Chạy lại với cache đó cho kết quả trùng 100%:
   `scripts\run_private.ps1 -Cache outputs\private_runs\<HHMM>\cache.sqlite`.

## 3. Khi có lỗi

| Dấu hiệu | Việc làm |
|---|---|
| `LỖI: HEAD ... không phải tag` | `git checkout private-final` rồi chạy lại |
| `LỖI: working tree có thay đổi` | `git stash` (không sửa code), chạy lại |
| `LỖI: không thấy data/private_test/questions.jsonl` | tải lại file câu hỏi của BTC |
| Đỏ: `N câu dùng fallback` (gateway 429/timeout/5xx) | đợi 5–10 phút rồi chạy lại **trên đúng cache của lần đó**: `-Cache outputs\private_runs\<HHMM>\cache.sqlite` (bash: `CACHE=...`). Câu đã ổn lấy từ cache (không đổi, không tốn tiền), chỉ câu lỗi được gọi lại vì kết quả fallback không được cache. Chạy KHÔNG có `-Cache` sẽ là một lần rút mới hoàn toàn |
| Fallback vẫn còn sau 3 lần chạy (gateway sập lâu) | file vẫn hợp lệ (câu lỗi dùng thứ hạng local + trích đoạn); thử lại sau 1–2 giờ; chỉ nộp file có fallback nếu đã gần hết ngày và chưa có file xanh nào |
| Đỏ: tỷ lệ từ chối / độ dài lệch xa | mở `outputs/private_HHMM_log.jsonl` xem `incidents`; không sửa code; nếu không có sự cố nào thì đề Private khác đề Public, vẫn nộp |
| `neorag run thất bại` (mất mạng giữa chừng) | chạy lại với `-Cache outputs\private_runs\<HHMM>\cache.sqlite` của lần dở: cache giữ các câu đã xong |
| Hết số dư | không chạy thêm; nộp file xanh gần nhất |

## 4. Phương án nhiều lần chạy và nộp bài

Mỗi lần chạy script KHÔNG có `-Cache` là **một lần rút độc lập** (cache mới, Haiku viết lại câu hỏi, rerank và trả
lời lại từ đầu; diễn tập cho thấy hai lần rút khác nhau ở > 50% top-5). Điểm Private xem được ngay sau khi nộp, nên:

1. Lần rút A (sáng sớm): chạy script → nếu xanh, nộp **lượt 1**, ghi điểm vào bảng.
2. Lần rút B: chạy script lần nữa (cache mới) → nếu xanh, nộp **lượt 2**, ghi điểm.
3. Lần rút C (tùy chọn): như trên, nộp **lượt 3**.
4. **Lượt cuối phải là file có điểm cao nhất**: nếu lần rút sau thấp hơn, nộp lại file tốt nhất (lấy từ
   `outputs/private_runs/<HHMM>/private_<HHMM>.zip`) ở lượt tiếp theo. Tối đa 3 lần rút để luôn còn **≥ 2 lượt dự
   phòng** (một để nộp lại file tốt nhất, một cho sự cố: bài Failed không tính lượt).
5. Không nộp file có cảnh báo đỏ khi đã có file xanh. Mỗi lần rút ~6 phút, ~$0.075: 3 lần rút ≈ $0.23.

| Lượt | Giờ | Lần rút (`outputs/private_runs/<HHMM>`) | File | sha256 (12 ký tự) | Sanity | Điểm Private | Ghi chú |
|---|---|---|---|---|---|---|---|
| 1 | | | | | | | |
| 2 | | | | | | | |
| 3 | | | | | | | |
| 4 | | | | | | | |
| 5 | | | | | | | |

Sau lượt cuối: kiểm tra trên trang thi rằng bài nộp gần nhất đúng là file điểm cao nhất (so sha256). Giữ nguyên thư
mục `outputs/private_runs/<HHMM>/` của file đó (cache + log) để đối chiếu khi BTC yêu cầu.

## 5. Sau khi nộp

- Ghi điểm Private vào `docs/experiments.md` (dòng E7, cột Private) vào ngày 09/11 trở đi.
- Không push code mới lên `main` trong ngày 08/11 (tag `private-final` đã cố định bản chạy).

## 6. Bản chốt và diễn tập

| Mục | Kết quả |
|---|---|
| Commit gắn tag `private-final` | ghi sau khi diễn tập (xem báo cáo CHECKPOINT B) |
| Diễn tập clone sạch, `-Cache` = cache E7 | khớp file Public E7 42/42, sanity xanh |
| Diễn tập clone sạch, cache mới (một lần rút) | sanity xanh, 0 fallback; số liệu trong `docs/experiments.md` |
