#!/usr/bin/env bash
# Chạy Private Test bằng một lệnh (Linux/macOS/Git Bash). Bản Windows: scripts/run_private.ps1.
#
#   bash scripts/run_private.sh                          # private_test, yêu cầu HEAD = tag private-final
#   SPLIT=public_test SKIP_TAG_CHECK=1 bash scripts/run_private.sh   # diễn tập
set -uo pipefail
SPLIT="${SPLIT:-private_test}"
TAG="${TAG:-private-final}"
cd "$(dirname "$0")/.."
export PYTHONIOENCODING=utf-8
fail() { printf '\033[91mLỖI: %s\033[0m\n' "$1"; exit 1; }
step() { printf '\033[96m==> %s\033[0m\n' "$1"; }

step "Kiểm tra mã nguồn"
HEAD_SHA=$(git rev-parse --short HEAD)
if [ -z "${SKIP_TAG_CHECK:-}" ]; then
  TAG_SHA=$(git rev-parse --short "$TAG^{commit}" 2>/dev/null) || fail "chưa có tag $TAG"
  [ "$TAG_SHA" = "$HEAD_SHA" ] || fail "HEAD ($HEAD_SHA) không phải tag $TAG ($TAG_SHA). Chạy: git checkout $TAG"
fi
[ -z "$(git status --porcelain --untracked-files=no)" ] || fail "working tree có thay đổi chưa commit"
echo "    commit $HEAD_SHA, working tree sạch"
QUESTIONS="data/$SPLIT/questions.jsonl"
[ -f "$QUESTIONS" ] || fail "không thấy $QUESTIONS"
echo "    $QUESTIONS ($(grep -c . "$QUESTIONS") câu)"
[ -f .env ] || fail "không thấy file .env (chứa key gateway)"
echo "    có file .env"

step "Nạp configs/private.env"
while IFS= read -r line || [ -n "$line" ]; do
  line="${line%$'\r'}"
  case "$line" in ''|'#'*) continue ;; RAG_*=*) ;; *) fail "configs/private.env chỉ được chứa biến RAG_* (gặp $line)" ;; esac
  export "${line?}"
  echo "    $line"
done < configs/private.env

if [ -x .venv/Scripts/python.exe ]; then PY=.venv/Scripts/python.exe
elif [ -x .venv/bin/python ]; then PY=.venv/bin/python
else PY=python; fi
SHORT="${SPLIT%_test}"
STAMP=$(date +%H%M)
BASE="outputs/${SHORT}_$STAMP"; n=1
while [ -e "$BASE.zip" ] || [ -e "${BASE}_pred.jsonl" ]; do BASE="outputs/${SHORT}_${STAMP}_$n"; n=$((n+1)); done
PRED="${BASE}_pred.jsonl"; LOG="${BASE}_log.jsonl"; ZIP="$BASE.zip"
export RAG_LOG_PATH="$LOG"

step "Chạy pipeline ($SPLIT)"
START=$(date +%s)
"$PY" -m neorag.cli run "$SPLIT" --pipeline solution.pipeline:SolutionPipeline --out "$PRED" \
  || fail "neorag run thất bại. Chạy lại script: cache giữ các câu đã xong."
MINUTES=$(( ($(date +%s) - START + 30) / 60 ))

step "Kiểm tra định dạng"
"$PY" -m neorag.cli validate "$SPLIT" --predictions "$PRED" || fail "file predictions không hợp lệ"

step "Sanity check"
"$PY" scripts/sanity_check.py --pred "$PRED" --log "$LOG" --questions "$QUESTIONS"; SANE=$?

"$PY" -c "import sys, zipfile; z = zipfile.ZipFile(sys.argv[1], 'w', zipfile.ZIP_DEFLATED); z.write(sys.argv[2], sys.argv[3]); z.close()" \
  "$ZIP" "$PRED" "${SPLIT}_pred.jsonl" || fail "không tạo được $ZIP"
rm -f "${BASE}_submission.zip"
HASH=$("$PY" -c "import hashlib, sys; print(hashlib.sha256(open(sys.argv[1], 'rb').read()).hexdigest()[:12])" "$ZIP")
echo
echo "Thời gian chạy: ~$MINUTES phút · commit $HEAD_SHA · sha256 $HASH"
if [ "$SANE" -eq 0 ]; then printf '\033[92mSẴN SÀNG NỘP: %s\033[0m\n' "$ZIP"
else printf '\033[91mCÓ CẢNH BÁO ĐỎ, CHƯA NỘP: %s (xem docs/private-day.md)\033[0m\n' "$ZIP"; exit 2; fi
