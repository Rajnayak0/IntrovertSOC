# Convenience wrapper to start a llamafile server for IntrovertSOC.
# The llamafile binary and GGUF model are NOT bundled (see NETWORK.md) - point
# this script at your own copies.
#
#   .\scripts\start_llamafile.ps1 -Binary "C:\models\llamafile.exe" -Model "C:\models\Qwen3-4B-Q4_K_M.gguf"
#   # or set LLAMAFILE / LLAMAFILE_MODEL_PATH in your environment

param(
    [string]$Binary = $env:LLAMAFILE,
    [string]$Model = $env:LLAMAFILE_MODEL_PATH,
    [int]$Port = 8080,
    [string]$Host = "127.0.0.1"
)

if (-not $Binary) { Write-Error "Missing llamafile binary: pass -Binary or set LLAMAFILE."; exit 1 }
if (-not $Model)  { Write-Error "Missing GGUF model: pass -Model or set LLAMAFILE_MODEL_PATH."; exit 1 }
if (-not (Test-Path $Binary)) { Write-Error "Binary not found: $Binary"; exit 1 }
if (-not (Test-Path $Model))  { Write-Error "Model not found: $Model"; exit 1 }

Write-Output "Starting local LLM at http://${Host}:${Port} (loopback only)"
& $Binary -m $Model --server --host $Host --port $Port
