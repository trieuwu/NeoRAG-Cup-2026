# Giao diện chatbot S2B Hỏi Đáp

Frontend (Vite + React + TypeScript) dựng từ bàn giao Claude Design ([`design/s2b-ui/HANDOFF.md`](../design/s2b-ui/HANDOFF.md)),
gọi API trong [`app/api.py`](../app/api.py). Hợp đồng sự kiện SSE và dữ liệu `done`: [README mục 6](../README.md#6-chatbot).

## Chạy

```bash
# 1. API (thư mục gốc repo, môi trường Python đã cài .[api])
uvicorn app.api:app --port 8000

# 2. Giao diện
cd web
npm install
npm run dev            # http://localhost:5173, /api được chuyển tới :8000 (đổi bằng VITE_API_PROXY)
```

Bản build tĩnh: `npm run build` (ra `web/dist/`), phục vụ cùng origin với API hoặc đặt `NEORAG_CORS_ORIGINS` cho API.

Kiểm tra: `npm run typecheck`, `npm test` (bộ phân tích SSE, tách trích dẫn, ánh xạ CLB, tô số liệu).

## Cấu trúc

| Tệp | Vai trò |
|---|---|
| `src/styles/s2b.css` | token + class component, chép nguyên từ `design/s2b-ui/tokens/s2b.css` (sáng/tối qua `data-theme`) |
| `src/lib/sse.ts` | `fetch` + `ReadableStream`, bộ phân tích `event:`/`data:` chịu được mảnh bị cắt |
| `src/lib/useChat.ts` | vòng đời một câu hỏi: 4 bước (giữ mỗi bước ≥ 250 ms), token, `incident`, `ping`, đồng hồ 90 giây, Dừng, Thử lại |
| `src/lib/model.ts` | lịch sử hội thoại trong `localStorage` (server không lưu) |
| `src/components/*` | Sidebar, Hero, BotMessage (thanh bước, câu trả lời, `[n]`, nguồn, từ chối, lỗi, phản hồi), Composer, Panel (Nguồn + 4 tab Kỹ thuật) |

## Hành vi chính

- `[n]` hiện dạng chữ khi đang stream, thành nút bấm (mở panel Nguồn) khi nhận `done`.
- `abstained=true`: khung viền nét đứt, "Thông tin gần nhất" = 2 citation đầu.
- `incident retry`: thẻ đỏ đếm ngược `wait_s`, bước tương ứng đỏ; sự kiện tiếp theo xóa thẻ. `incident fallback`: dòng
  ghi chú dưới câu trả lời. Danh sách rerank rỗng (câu ngoài tài liệu) không bị báo là lỗi gateway.
- 90 giây không có sự kiện nào (kể cả `ping`) → "Câu trả lời mất quá nhiều thời gian" + Thử lại.
- Dừng: huỷ fetch, giữ phần đã stream, nhãn "Đã dừng" (server dừng ở ranh giới bước/token kế tiếp).
- Phím tắt: `/` ô nhập, Enter gửi, Shift+Enter xuống dòng, Esc đóng, ↑/↓ chuyển nguồn, Ctrl/Cmd+K mới, Ctrl/Cmd+. kỹ thuật.
- Mục "Mô phỏng tình huống": quá tải và hết thời gian chờ được mô phỏng phía client; câu ngoài tài liệu và câu
  trả lời dài là câu hỏi thật (câu mới tốn ≈ $0.002).

Khác với bàn giao: không dùng Tailwind vì `s2b.css` đã có đủ token và class component của thiết kế (dùng thẳng, tránh
hai nguồn sự thật). Thông tin không lấy từ backend (bảng so sánh, đoạn tô sẵn) được thay bằng: câu trả lời văn bản,
tô các con số/cụm trong ngoặc kép trùng giữa nguồn và câu trả lời.

Thư mục này độc lập với pipeline: pytest chỉ quét `tests/`, ruff chỉ kiểm tra `.py`, `neorag run` và bản
`private-final` không đọc `web/`.
