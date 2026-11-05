# Bàn giao giao diện S2B Hỏi Đáp → Claude Code

> Đọc file này đầu tiên. Nguồn thiết kế: canvas Claude Design "S2B Hỏi Đáp — Giao diện RAG" (người dùng giữ link).
> Mọi ràng buộc trong `.claude/CLAUDE.md` của repo vẫn áp dụng. Khi file này và tài liệu BTC khác nhau, tài liệu BTC đúng.

## 1. Mục tiêu

Dựng frontend thật gọi vào `uvicorn app.api:app`, phục vụ demo/pitching: người dùng hỏi nhanh có nguồn, và "Chế độ kỹ thuật" cho thấy bên trong pipeline.

Đặt code ở `web/` (gốc repo), có `package.json` riêng. Thêm `web/node_modules/`, `web/dist/` vào `.gitignore`.
Stack đề xuất: Next.js (hoặc Vite + React) + Tailwind. **Không sửa `src/neorag/`, `configs/eval.toml`, `src/neorag/metrics/`, `src/neorag/evaluate.py`**, và không sửa các nhánh code mà bản Private dùng (`pipeline.py`, `retrieval.py`, `query.py`, `rerank.py`, `prompts.py`, `resilience.py`). Tag `private-final` giữ nguyên.

## 2. Nội dung thư mục này

| Đường dẫn | Dùng để |
|---|---|
| `tokens/s2b.css` | Nguồn sự thật cho token (CSS variable, sáng/tối) và class component. Chuyển sang Tailwind theo mục 6. |
| `prototype/Main.dc.html` | Prototype bấm được (định dạng Claude Design, KHÔNG chạy trực tiếp). Đọc để biết hành vi, state, markup từng component. |
| `prototype/DesignSystem.dc.html` | Trang design system: màu, chữ, khoảng cách, component, bảng ánh xạ SSE. |
| `prototype/s2b-data.js` | Dữ liệu GIẢ + logic dựng trace giả. Chỉ để tham chiếu, không đưa vào web/. |
| `contract/response.example.json` | Mẫu sự kiện `done` mà giao diện hiển thị (nội dung là dữ liệu giả, trừ ngày 09/10/2011 của ProPTIT). |
| `contract/response.abstain.example.json` | Mẫu khi `abstained=true`. |

Chưa có ảnh chụp màn hình trong `screenshots/`; xem trực tiếp trên canvas.

## 3. Kết nối backend (đã chốt, ưu tiên hơn mọi chỗ khác nếu mâu thuẫn)

- `POST /api/chat`, body `{"message": "...", "cite": true}`, trả SSE (`text/event-stream`). Đọc bằng `fetch` + `ReadableStream`, **không dùng EventSource**. Định dạng: `event: <loại>\ndata: <json>\n\n`.
- Sự kiện: `stage {name, status: start|done, ms?}`, `token {text}`, `incident {type, stage, attempt, wait_s}`, `ping`, `done {...}`, `error {message}`.
- `name` của stage: `rewrite`, `retrieve`, `rerank`, `generate` ↔ 4 bước "Hiểu câu hỏi", "Tìm tài liệu", "Xếp hạng", "Soạn câu trả lời". `ms` chỉ có ở `done`.
- Trích dẫn `[n]` nằm trong chuỗi `token` (có thể bị cắt giữa token: phải gộp đệm). Danh sách nguồn chỉ có khi nhận `done` → **thẻ nguồn xuất hiện sau khi stream xong**; trong lúc stream, `[n]` hiện dạng chữ thường, chưa bấm được.
- Mỗi câu hỏi độc lập: không có hội thoại nối tiếp. Lịch sử chỉ lưu phía client (localStorage).
- Endpoint khác: `GET /api/health` (gọi một lần lúc khởi động để làm nóng), `GET /api/suggestions`, `GET /api/doc/{id}`. CORS mặc định mở (`NEORAG_CORS_ORIGINS`).
- Câu hỏi tối đa 500 ký tự (giao diện tự giới hạn dù server cho 1000); chuỗi chỉ toàn khoảng trắng coi như rỗng (giao diện chặn, vì server không chặn).

### Ánh xạ sự kiện → giao diện

| Sự kiện | Giao diện |
|---|---|
| `stage start` | Bước chuyển Chờ → Đang chạy (spinner nhỏ, màu nhấn) |
| `stage done` | Bước Xong: ✓ + `ms` (vd. "120 ms") |
| `token` | Stream từng chữ, con trỏ nhấp nháy, vùng `aria-live="polite"`. Bước 4 đang chạy |
| `incident` với `type=retry` | Thẻ đỏ nhạt "Hệ thống đang quá tải, thử lại sau ít giây.", đếm ngược theo `wait_s`; bước tương ứng đỏ. Không phải HTTP 429 thật: backend tự thử lại |
| `ping` | Không đổi giao diện; chỉ reset đồng hồ chờ |
| `done` | Thanh bước thu thành 1 dòng `✓ 4 bước · 1,84 s · 3 nguồn` (bấm để mở lại); hiện dải nguồn, hàng hành động; `[n]` thành bấm được |
| `done` với `abstained=true` | Thay văn bản đã stream bằng khung viền nét đứt hổ phách. Mục "Thông tin gần nhất" lấy **2 citation đầu** (`cited=false`) |
| `error` | Thẻ lỗi + nút "Thử lại" |
| 90 giây không có sự kiện nào (kể cả `ping`) | "Câu trả lời mất quá nhiều thời gian." + "Thử lại"; huỷ fetch |
| Bấm Dừng | Client huỷ fetch, giữ phần đã stream, nhãn mờ "Đã dừng". (Server vẫn chạy hết và ghi cache) |

Lưu ý: `abstained` do backend dò chuỗi ("không có thông tin" / "không đề cập") nên có thể dương tính giả với câu trả lời một phần. Chấp nhận.

## 4. Quy tắc hiển thị dữ liệu (quan trọng)

1. **Tab Truy xuất**: 20 ứng viên (không phải 30). Dòng chảy: "20 ứng viên → N được chọn → k được trích dẫn". Cột BM25 / Dense / Rerank hiển thị **HẠNG** (`#1`, `#2`…, `—` nếu null), **không có thanh bar điểm**; tô đậm khi hạng ≤ 5. Dòng được trích dẫn có nền nhấn + nhãn "Trích dẫn"; dòng trong ngữ cảnh: nhãn "Đã chọn"; còn lại mờ. Bấm tiêu đề cột để sắp xếp.
2. `citations[].score` là điểm RRF nội bộ: **không** hiển thị như phần trăm hay độ tin cậy.
3. Token và chi phí là **ước tính**: ghi nhãn "≈" (vd. `≈ 1 830 / 96`, `≈ $0.0021`). Dòng mono dưới câu trả lời (khi bật Chế độ kỹ thuật): `1 840 ms · 2 lời gọi LLM · ≈$0.0021`.
4. Thẻ "Lời gọi trúng cache" = `llm_cache_hits / llm_calls` (backend không có boolean `cache_hit`).
5. **Không có chip lọc CLB trong composer.** Chip CLB ở màn trống (Tất cả · ProPTIT · Multimedia · GCC) chỉ lọc danh sách câu hỏi gợi ý, không gửi kèm khi hỏi. Tab Truy vấn hiển thị `trace.clubs` do bước viết lại suy ra.
6. Thanh bước, abstain, lỗi: hành vi như prototype. Câu trúng cache xong trong ~170 ms nên spinner gần như không thấy: đặt thời gian hiển thị tối thiểu ~250 ms mỗi bước khi demo.

## 5. Việc backend cần (chỉ làm nếu cần, và chỉ trong `app/api.py`, `src/solution/trace.py`)

- Thêm `club` và `topic` vào từng phần tử `trace.candidates` (`trace.py` quanh dòng 143–151). Nếu chưa làm, giao diện có thể tra `GET /api/doc/{id}` làm phương án tạm.
- Tuỳ chọn: heartbeat/`ping` định kỳ khi chờ gateway (để đồng hồ 90 giây có ý nghĩa), và cờ huỷ khi client ngắt kết nối.
- Mọi thay đổi này không chạm đường chạy Private. Sau mỗi lần merge, chạy lại compare_predictions trên public_test để chắc chắn vẫn khớp 42/42.

## 6. Token → Tailwind

Dùng CSS variable trong `tokens/s2b.css`; bật dark mode bằng thuộc tính `data-theme="dark"` trên phần tử gốc.

```ts
// tailwind.config.ts (rút gọn)
export default {
  darkMode: ['selector', '[data-theme="dark"]'],
  theme: { extend: {
    fontFamily: { ui: ['Be Vietnam Pro', 'system-ui'], mono: ['JetBrains Mono', 'monospace'] },
    colors: {
      app: 'var(--bg)',
      surface: { DEFAULT: 'var(--surface)', 2: 'var(--surface-2)', 3: 'var(--surface-3)' },
      line: { DEFAULT: 'var(--border)', strong: 'var(--border-strong)' },
      ink: { DEFAULT: 'var(--text)', 2: 'var(--text-2)', 3: 'var(--text-3)' },
      accent: { DEFAULT: 'var(--accent)', hover: 'var(--accent-hover)', soft: 'var(--accent-soft)' },
      club: {
        pro: { bg: 'var(--pro-bg)', fg: 'var(--pro-fg)', solid: 'var(--pro-solid)' },
        mm:  { bg: 'var(--mm-bg)',  fg: 'var(--mm-fg)',  solid: 'var(--mm-solid)' },
        gcc: { bg: 'var(--gcc-bg)', fg: 'var(--gcc-fg)', solid: 'var(--gcc-solid)' },
        s2b: { bg: 'var(--s2b-bg)', fg: 'var(--s2b-fg)', solid: 'var(--s2b-solid)' },
      },
    },
    borderRadius: { card: '12px', ctl: '8px', pill: '999px' },
    spacing: { 1: '4px', 2: '8px', 3: '12px', 4: '16px', 5: '20px', 6: '24px', 8: '32px', 10: '40px', 12: '48px' },
    transitionDuration: { DEFAULT: '160ms' },
    transitionTimingFunction: { DEFAULT: 'cubic-bezier(.16,.84,.44,1)' },
  } },
}
```

Tên component React ↔ class gốc: `ChipFilter` (.chip), `ClubBadge` (.badge .club--*), `CiteMark` (.cite), `SourceCard` (.src-mini / .src-card), `StepProgress` (.steps), `AnswerBlock` (.answer), `CompareTable` (.tbl), `CandidateTable` (.ctbl), `ErrorCard` (.errcard), `AbstainCard` (.abstain), `Composer` (.composer), `SourcePanel` / `TechPanel` (.panel, .tabs).

## 7. Bố cục, chuyển động, truy cập (tóm tắt, chi tiết xem prototype)

- Desktop ≥ 1280: sidebar 260px (thu về 64px) · chat tối đa 760px · panel phải 400px trượt từ phải, cột chat co lại. Tablet 768–1279: sidebar thành drawer, panel thành overlay. Mobile < 768: Nguồn và Chế độ kỹ thuật là bottom sheet kéo được (nửa màn → toàn màn).
- Chuyển động 150–200ms ease-out; tôn trọng `prefers-reduced-motion`.
- Phím tắt: `/` focus ô nhập, Enter gửi, Shift+Enter xuống dòng, Esc đóng panel, ↑/↓ chuyển nguồn, Ctrl/Cmd+K cuộc trò chuyện mới, Ctrl/Cmd+. bật/tắt Chế độ kỹ thuật. Không dùng global keydown ở prototype; ở app thật có thể gắn ở `window`.
- Số trích dẫn: `aria-label="Nguồn 1: ProPTIT, đoạn 12"`; vùng stream `aria-live="polite"`; vùng chạm ≥ 44px trên mobile; focus ring rõ.
- Không dùng logo hay nhận diện thật của PTIT/CLB: chỉ màu và chữ viết tắt trong badge.
- Toàn bộ giao diện tiếng Việt.

## 8. Thứ tự làm đề xuất

1. Thêm `club`/`topic` vào `trace.candidates` (nếu chọn sửa backend); cập nhật test liên quan trong `tests/`.
2. Dựng `web/`: token + Tailwind, layout 3 cột, sidebar lịch sử (localStorage), màn trống, composer.
3. Client SSE (`fetch` + `ReadableStream`, bộ phân tích `event:`/`data:`, gộp token, nhận `[n]`), thanh 4 bước, stream, dải nguồn, panel Nguồn.
4. Abstain, lỗi (incident/retry, error, 90 giây), Dừng, phản hồi 👍/👎 (chỉ phía client trừ khi có endpoint).
5. Chế độ kỹ thuật (4 tab), responsive tablet/mobile, dark mode, kiểm tra truy cập.
6. Chạy thử với câu đã cache; câu mới tốn khoảng $0.002 mỗi câu. Ngân sách 5 USD cho cả giải.

## 9. Git

Nhánh `feat/giao-dien-s2b`; commit Conventional Commits, type/scope tiếng Anh, mô tả tiếng Việt có dấu (vd. `feat(web): dựng giao diện chat S2B Hỏi Đáp`). Không ghi co-author hay attribution của AI. Không `git push` khi chưa được người dùng yêu cầu. **Không sửa mã trong ngày 08/11.**
