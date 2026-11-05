# Giao diện chatbot

Frontend của chatbot (thiết kế bằng Claude Design), gọi API trong [`app/api.py`](../app/api.py).

- Chạy API: `uvicorn app.api:app --port 8000` (cài: `pip install -e ".[api]"`).
- Hợp đồng sự kiện SSE và dữ liệu `done`: [README mục 6](../README.md#6-chatbot).
- Thư mục này độc lập với pipeline: pytest chỉ quét `tests/`, ruff chỉ kiểm tra file `.py`, `neorag run` và bản
  `private-final` không đọc `web/`.
- `node_modules/`, `dist/`, `build/`, `.next/`, `.env*` trong thư mục này đã được gitignore.
