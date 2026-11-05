# Chạy Private Test bằng một lệnh (Windows PowerShell 5.1+). Kịch bản ngày thi: docs/private-day.md
#
#   powershell -ExecutionPolicy Bypass -File scripts\run_private.ps1
#   powershell -ExecutionPolicy Bypass -File scripts\run_private.ps1 -Split public_test -SkipTagCheck   # diễn tập
#   ... -Cache outputs\private_runs\0730\cache.sqlite   # chạy lại đúng lần rút 0730 (vd. sau khi có fallback)
#   ... -Cache .cache\solution.sqlite                      # dùng cache chung (diễn tập khớp file đã nộp)
#
# Mặc định mỗi lần chạy dùng một cache MỚI (outputs/<bộ>_runs/<HHMM>/cache.sqlite) = một lần rút độc lập.
# Sau khi chạy, pred + log + zip + cache được sao lưu vào outputs/<bộ>_runs/<HHMM>/.
#
# Các bước: kiểm tra tag private-final, working tree sạch, file câu hỏi, .env (chỉ kiểm tra tồn tại)
# -> nạp configs/private.env -> neorag run -> validate -> sanity check -> outputs/<bộ>_<HHMM>.zip (không ghi đè).
param(
    [string]$Split = "private_test",
    [string]$Tag = "private-final",
    [string]$Cache = "",
    [switch]$SkipTagCheck
)

$ErrorActionPreference = "Continue"  # lỗi của lệnh ngoài kiểm tra bằng $LASTEXITCODE
$env:PYTHONIOENCODING = "utf-8"
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
Set-Location (Split-Path -Parent $PSScriptRoot)

function Fail([string]$msg) {
    Write-Host "LỖI: $msg" -ForegroundColor Red
    exit 1
}

function Step([string]$msg) { Write-Host "==> $msg" -ForegroundColor Cyan }

# ---------------------------------------------------------------- kiểm tra trước khi chạy
Step "Kiểm tra mã nguồn"
$head = (git rev-parse --short HEAD).Trim()
if (-not $SkipTagCheck) {
    $tagCommit = (git rev-parse --short "$Tag^{commit}" 2>$null)
    if (-not $tagCommit) { Fail "chưa có tag $Tag" }
    if ($tagCommit.Trim() -ne $head) { Fail "HEAD ($head) không phải tag $Tag ($tagCommit). Chạy: git checkout $Tag" }
}
$dirty = git status --porcelain --untracked-files=no
if ($dirty) { Fail "working tree có thay đổi chưa commit:`n$dirty" }
Write-Host "    commit $head, working tree sạch"

$questions = "data/$Split/questions.jsonl"
if (-not (Test-Path $questions)) { Fail "không thấy $questions" }
$nQuestions = (Get-Content $questions -Encoding UTF8 | Where-Object { $_.Trim() }).Count
Write-Host "    $questions ($nQuestions câu)"

if (-not (Test-Path ".env")) { Fail "không thấy file .env (chứa key gateway)" }
Write-Host "    có file .env"

# ---------------------------------------------------------------- cấu hình đóng băng
Step "Nạp configs/private.env"
foreach ($line in Get-Content "configs/private.env" -Encoding UTF8) {
    $line = $line.Trim()
    if (-not $line -or $line.StartsWith("#")) { continue }
    $name, $value = $line.Split("=", 2)
    if ($name -notmatch "^RAG_") { Fail "configs/private.env chỉ được chứa biến RAG_* (gặp $name)" }
    Set-Item -Path "env:$name" -Value $value
    Write-Host "    $name=$value"
}

# ---------------------------------------------------------------- chạy
$python = if (Test-Path ".venv/Scripts/python.exe") { ".venv/Scripts/python.exe" } else { "python" }
$short = $Split -replace "_test$", ""
$stamp = Get-Date -Format "HHmm"
$base = "outputs/${short}_$stamp"
$name = $stamp
$n = 1
while ((Test-Path "$base.zip") -or (Test-Path "${base}_pred.jsonl") -or (Test-Path "outputs/${short}_runs/$name")) {
    $name = "${stamp}_$n"; $base = "outputs/${short}_$name"; $n++
}
$pred, $log, $zip = "${base}_pred.jsonl", "${base}_log.jsonl", "$base.zip"
$runDir = "outputs/${short}_runs/$name"
if (-not $Cache) { $Cache = "$runDir/cache.sqlite" }
elseif (-not (Test-Path $Cache)) { Fail "không thấy cache $Cache" }
New-Item -ItemType Directory -Force -Path $runDir | Out-Null
$env:RAG_LOG_PATH = $log
$env:RAG_CACHE_PATH = $Cache
Write-Host "    lần chạy $name, cache: $Cache"

Step "Chạy pipeline ($Split)"
$started = Get-Date
& $python -m neorag.cli run $Split --pipeline solution.pipeline:SolutionPipeline --out $pred
if ($LASTEXITCODE -ne 0) { Fail "neorag run thất bại (mã $LASTEXITCODE). Chạy lại script: cache giữ các câu đã xong." }
$minutes = [math]::Round(((Get-Date) - $started).TotalMinutes, 1)

Step "Kiểm tra định dạng"
& $python -m neorag.cli validate $Split --predictions $pred
if ($LASTEXITCODE -ne 0) { Fail "file predictions không hợp lệ" }

Step "Sanity check"
& $python scripts/sanity_check.py --pred $pred --log $log --questions $questions
$sane = $LASTEXITCODE -eq 0

# Tên file bên trong zip giống hệt `neorag run` (<split>_pred.jsonl); bỏ zip phụ do neorag tạo để tránh nộp nhầm.
& $python -c "import sys, zipfile; z = zipfile.ZipFile(sys.argv[1], 'w', zipfile.ZIP_DEFLATED); z.write(sys.argv[2], sys.argv[3]); z.close()" $zip $pred "${Split}_pred.jsonl"
if ($LASTEXITCODE -ne 0) { Fail "không tạo được $zip" }
Remove-Item "${base}_submission.zip" -ErrorAction SilentlyContinue
$hash = (Get-FileHash $zip -Algorithm SHA256).Hash.Substring(0, 12)
Copy-Item $pred, $log, $zip -Destination $runDir
if ((Resolve-Path $Cache).Path -ne (Join-Path (Resolve-Path $runDir).Path "cache.sqlite")) {
    Copy-Item $Cache -Destination "$runDir/cache.sqlite"
}
Write-Host "Sao lưu lần chạy: $runDir (pred, log, zip, cache.sqlite)"
Write-Host ""
Write-Host "Thời gian chạy: $minutes phút · commit $head · sha256 $hash"
if ($sane) {
    Write-Host "SẴN SÀNG NỘP: $zip" -ForegroundColor Green
} else {
    Write-Host "CÓ CẢNH BÁO ĐỎ, CHƯA NỘP: $zip (xem docs/private-day.md)" -ForegroundColor Red
    exit 2
}
