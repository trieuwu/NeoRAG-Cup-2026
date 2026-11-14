# Khởi động bản Demo S2B Hỏi Đáp (giao diện React + FastAPI SSE trên một cổng duy nhất).
#
#   powershell -ExecutionPolicy Bypass -File .\start_demo.ps1
#   powershell -ExecutionPolicy Bypass -File .\start_demo.ps1 -SkipBuild
#   powershell -ExecutionPolicy Bypass -File .\start_demo.ps1 -Port 8000
param(
    [int]$Port = 8000,
    [string]$BindHost = "127.0.0.1",
    [switch]$SkipBuild
)

$ErrorActionPreference = "Continue"
$env:PYTHONIOENCODING = "utf-8"
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
Set-Location $PSScriptRoot

function Fail([string]$msg) {
    Write-Host "LỖI: $msg" -ForegroundColor Red
    exit 1
}

function Step([string]$msg) { Write-Host "==> $msg" -ForegroundColor Cyan }

if (-not (Test-Path ".env")) {
    Fail "không thấy file .env (chứa key gateway). Sao chép từ .env.example và điền key trước khi chạy."
}

if (Test-Path "configs/private.env") {
    Step "Nạp cấu hình bản chốt Private 88.79 (configs/private.env)"
    foreach ($line in Get-Content "configs/private.env" -Encoding UTF8) {
        $line = $line.Trim()
        if (-not $line -or $line.StartsWith("#")) { continue }
        $name, $value = $line.Split("=", 2)
        if ($name -match "^RAG_") {
            Set-Item -Path "env:$name" -Value $value
            Write-Host "    $name=$value"
        }
    }
}

if (-not $SkipBuild) {
    Step "Build giao diện web (web/ -> web/dist/)"
    Push-Location "web"
    try {
        if (-not (Test-Path "node_modules")) {
            Write-Host "    Cài đặt gói npm cho web/..."
            npm ci
            if ($LASTEXITCODE -ne 0) { Fail "npm ci thất bại" }
        }
        npm run build
        if ($LASTEXITCODE -ne 0) { Fail "npm run build thất bại" }
    } finally {
        Pop-Location
    }
} elseif (-not (Test-Path "web/dist/index.html")) {
    Fail "chưa có web/dist/index.html. Hãy chạy lại không kèm -SkipBuild."
}

$python = if (Test-Path ".venv/Scripts/python.exe") { ".venv/Scripts/python.exe" } else { "python" }

Step "Khởi động FastAPI + Giao diện S2B Hỏi Đáp tại http://${BindHost}:${Port}"
& $python -m uvicorn app.api:app --host $BindHost --port $Port
