# 🛡️ IntrovertSOC

> **The 100% Offline, Privacy-First, Air-Gapped AI Security Operations Center (SOC)**  
> Alert triage, case management, AI incident investigation, threat enrichment, and automated playbooks — powered entirely by a local LLM engine. **Zero cloud API keys. Zero external telemetry. Zero subscription costs.**

---

## 📑 Table of Contents
1. [🎯 Aim & Motive](#-aim--motive)
2. [✨ Key Features & Chat Modes](#-key-features--chat-modes)
3. [🧠 Best Models & Hardware Requirements](#-best-models--hardware-requirements)
4. [📋 Prerequisites](#-prerequisites)
5. [📦 Step-by-Step Installation](#-step-by-step-installation)
6. [🖱️ One-Click Batch Files (.bat) — Copy & Paste Scripts](#️-one-click-batch-files-bat--copy--paste-scripts)
   - [1. `setup.bat` (One-Time Setup)](#1-setupbat-one-time-setup)
   - [2. `start.bat` (One-Click Launch)](#2-startbat-one-click-launch)
   - [3. `stop.bat` (One-Click Shutdown)](#3-stopbat-one-click-shutdown)
   - [4. `local-paths.bat` (Optional Path Override)](#4-local-pathsbat-optional-path-override)
7. [🚀 How to Use IntrovertSOC](#-how-to-use-introvertsoc)
8. [🔧 Troubleshooting & Common Issues](#-troubleshooting--common-issues)
9. [📜 Attribution & License](#-attribution--license)

---

## 🎯 Aim & Motive

### The Problem
Traditional Cloud AI SOC tools (and extensions relying on external APIs like OpenAI, Anthropic, or cloud providers) require sending your organization's sensitive security telemetry — **internal IP addresses, raw syslog dumps, firewall alerts, credentials, and vulnerability signatures** — across the public internet to third-party servers.

For cybersecurity teams, defense contractors, financial institutions, and privacy-conscious enterprises, this creates severe compliance violations (**GDPR, HIPAA, SOC 2, ISO 27001**) and poses significant data-leak risks.

### The Solution: IntrovertSOC
**IntrovertSOC** reimagines the modern agentic SOC platform as a **strictly self-contained, air-gapped system**:
- **100% Local Intelligence:** All alert summaries, case assessments, playbook logic, and threat triage are executed on your machine via a local `llamafile` / llama.cpp inference server.
- **No Cloud Dependencies:** No OpenAI API keys, no monthly token bills, and no third-party telemetry. It talks exclusively to `127.0.0.1`.
- **Lightweight Architecture:** Stripped of heavy distributed infrastructure (no Postgres, Redis, Kafka, or LDAP required). Runs efficiently on top of **SQLite** and Python background worker threads.
- **Fast Modern UI:** Built with **React 19** and **Tailwind CSS 4** featuring an analyst-first dark mode.

---

## ✨ Key Features & Chat Modes

IntrovertSOC features three unique **LLM Persona Modes** that you can toggle directly from the top navigation bar at any time:

| Mode | Personality | Best For |
|---|---|---|
| 💼 **Work Mode** | Comprehensive, structured markdown reports with executive summaries, risk levels, and MITRE ATT&CK mapping. | Formal incident response documentation and management reporting. |
| 🤫 **Introvert Mode** | Direct, factual, stripped of conversational pleasantries and filler text. | Fast day-to-day tier-1/tier-2 alert triage. |
| ⚡ **Super Introvert** | Maximum brevity — clipped 1 to 2-line tactical answers. | Rapid fire command-line style triage when every second counts. |

---

## 🧠 Best Models & Hardware Requirements

IntrovertSOC uses **GGUF** quantized models executed through **llamafile** (or any OpenAI-compatible local server on port 8080).

### What is Quantization (`Q4_K_M`)?
Quantization compresses large model weights from 16-bit floating point down to 4-bit integers.  
👉 **`Q4_K_M` is the recommended sweet spot**: it reduces model size by ~70% while retaining over 98% of full analytical precision.

### Hardware Tier & Recommended Model Matrix

| Hardware Tier | Available System RAM / VRAM | Recommended Model | Model Size | Why Choose This? |
|---|---|---|---|---|
| **Entry-Level (Standard Laptop)** | **4 GB – 8 GB RAM** | **Qwen3-4B-Instruct (`Q4_K_M`)** ⭐ *(Default)* | **~2.49 GB** | Runs on virtually any computer. Fast response times, low RAM usage, and solid triage capabilities. |
| **Budget / Ultra-Light** | 2 GB – 4 GB RAM | **Qwen3-1.7B-Instruct (`Q4_K_M`)** | ~1.2 GB | For resource-constrained mini-PCs or older systems. |
| **Mid-Range (Standard Workstation)** | **16 GB RAM** (or 8GB GPU) | **Qwen3-8B-Instruct (`Q4_K_M`)** | ~4.7 GB | Noticeably sharper case assessments, reliable JSON structured outputs, and deeper threat correlation. |
| **Heavy Analyst Rig** | 16 GB – 24 GB RAM | **Qwen3-14B-Instruct (`Q4_K_M`)** | ~9.0 GB | Superior playbook decision making and multi-step investigation logic. |
| **High-End Workstation** | 24 GB – 32 GB RAM | **Qwen3-32B-Instruct (`Q4_K_M`)** | ~20 GB | Enterprise-grade reasoning without any cloud connection. |
| **Enterprise Server** | 48 GB – 64 GB+ RAM | **Qwen3-72B-Instruct (`Q4_K_M`)** | ~43 GB | Flagship-class deep cyber threat intelligence extraction. |

### Where to Download the Model & llamafile
1. **Download `llamafile` executable:**
   - Grab the latest Windows release (`llamafile-x.x.x.exe`) from Mozilla's official GitHub:  
     👉 [llamafile Releases](https://github.com/Mozilla-Ocho/llamafile/releases)
   - Rename it to `llamafile.exe` and place it inside the `models/` folder (or project root).
2. **Download your GGUF Model:**
   - For the recommended starter model (**Qwen3-4B**):  
     👉 [Download Qwen3-4B-Q4_K_M.gguf from Hugging Face](https://huggingface.co/Qwen/Qwen3-4B-GGUF)
   - Save the `.gguf` file directly inside the `models/` directory.

---

## 📋 Prerequisites

Before running the application, make sure you have the following installed on Windows:

1. **Python Package Manager (`uv`)**  
   Open PowerShell or Command Prompt and run:
   ```powershell
   winget install astral-sh.uv
   ```
2. **Node.js (LTS version 20 or newer)**  
   ```powershell
   winget install OpenJS.NodeJS.LTS
   ```
3. *(Optional)* **Git for Windows** (already installed if you cloned this repository):
   ```powershell
   winget install Git.MinGit
   ```

---

## 📦 Step-by-Step Installation

1. **Clone or Download the Repository:**
   ```powershell
   git clone https://github.com/Rajnayak0/IntrovertSOC.git
   cd IntrovertSOC
   ```
2. **Place your Model and Engine:**
   - Place `llamafile.exe` inside the `models/` folder.
   - Place your chosen `.gguf` model file (e.g., `Qwen3-4B-Q4_K_M.gguf`) inside the `models/` folder.
3. **Run Setup:**
   - Double-click `setup.bat` (or execute it from terminal).
   - Enter your desired **Admin Username** and **Password** when prompted.
4. **Start IntrovertSOC:**
   - Double-click `start.bat`.
   - Your browser will open automatically at `http://127.0.0.1:5173`.

---

## 🖱️ One-Click Batch Files (.bat) — Copy & Paste Scripts

For Windows users, IntrovertSOC includes three pre-configured batch files in the root folder so you never have to type long terminal commands manually.

> **💡 How to create or edit a `.bat` file in Windows:**  
> 1. Open **Notepad** (press `Win + R`, type `notepad`, and press Enter).  
> 2. Copy the code block below and paste it into Notepad.  
> 3. Click **File → Save As...**  
> 4. In **Save as type**, choose **All Files (*.*)**.  
> 5. Enter the exact filename (e.g. `setup.bat`) and click **Save** in the `IntrovertSOC` project root folder.

---

### 1. `setup.bat` (One-Time Setup)
This script verifies your prerequisites (`uv` and `node`), synchronizes Python backend dependencies, creates database tables, lets you create an admin account, and installs frontend dependencies.

```bat
@echo off
setlocal EnableExtensions
cd /d "%~dp0"
title IntrovertSOC setup

echo ============================================
echo  IntrovertSOC - one-time setup
echo ============================================
echo.

where uv >nul 2>&1 || goto no_uv
where node >nul 2>&1 || goto no_node
where npm >nul 2>&1 || goto no_node

echo [1/3] Backend: installing Python dependencies...
pushd "%~dp0backend"
uv sync
if errorlevel 1 goto fail

echo.
echo [2/3] Database: creating tables...
uv run python manage.py migrate
if errorlevel 1 goto fail

echo.
echo [3/3] Creating your login account.
echo       (Username + password of your choice. Press Ctrl+C to skip if
echo        you already created one before.)
uv run python manage.py createsuperuser
popd

echo.
echo [3/3] Frontend: installing JavaScript dependencies (slow first time)...
pushd "%~dp0frontend"
call npm install
if errorlevel 1 goto fail
popd

echo.
echo ============================================
echo  SETUP DONE
echo  Next step: double-click start.bat
echo  (it opens the browser at http://127.0.0.1:5173)
echo ============================================
pause
exit /b 0

:no_uv
echo [MISSING] "uv" - the Python tool runner.
echo.
echo Install it first, then run setup.bat again:
echo    winget install astral-sh.uv
echo    (or see https://docs.astral.sh/uv/getting-started/installation/)
pause
exit /b 1

:no_node
echo [MISSING] Node.js / npm.
echo.
echo Install Node.js 20 or newer, then run setup.bat again:
echo    winget install OpenJS.NodeJS.LTS
echo    (or download from https://nodejs.org)
pause
exit /b 1

:fail
echo.
echo SETUP FAILED - read the error message above, fix it, run setup.bat again.
pause
exit /b 1
```

---

### 2. `start.bat` (One-Click Launch)
This script auto-detects `llamafile.exe` and any `.gguf` file in `models\`, starts the backend (:8000), frontend (:5173), and local LLM (:8080) in three separate windows, and opens your browser.

```bat
@echo off
setlocal EnableExtensions
cd /d "%~dp0"
title IntrovertSOC launcher

rem =====================================================================
rem Config - only needed if auto-detect gets it wrong. local-paths.bat
rem (created on first run) takes priority over anything set here.
rem =====================================================================
set "LLAMAFILE_EXE="
set "GGUF_MODEL="

rem --- Remembered paths from a previous run ---
if exist "%~dp0local-paths.bat" call "%~dp0local-paths.bat"

rem --- Auto-detect the llamafile binary ---
if not defined LLAMAFILE_EXE if exist "%~dp0llamafile.exe" set "LLAMAFILE_EXE=%~dp0llamafile.exe"
if not defined LLAMAFILE_EXE if exist "%~dp0models\llamafile.exe" set "LLAMAFILE_EXE=%~dp0models\llamafile.exe"
if not defined LLAMAFILE_EXE if defined LLAMAFILE set "LLAMAFILE_EXE=%LLAMAFILE%"

rem --- Auto-detect the first .gguf in models\ ---
if not defined GGUF_MODEL for %%F in ("%~dp0models\*.gguf") do if not defined GGUF_MODEL set "GGUF_MODEL=%%~fF"
if not defined GGUF_MODEL if defined LLAMAFILE_MODEL_PATH set "GGUF_MODEL=%LLAMAFILE_MODEL_PATH%"

rem --- check mode: print detection status, launch nothing ---
if /i "%~1"=="check" goto check

rem --- Refuse to start a second stack: two backends on one port cause session/CSRF mixups ---
netstat -ano | findstr /c:":8000 " | findstr LISTENING >nul 2>&1
if not errorlevel 1 goto already_running
netstat -ano | findstr /c:":5173 " | findstr LISTENING >nul 2>&1
if not errorlevel 1 goto already_running

rem --- Ask once for whatever is still missing, then remember it ---
if not defined LLAMAFILE_EXE (
    echo No llamafile binary found.
    set /p "LLAMAFILE_EXE=Full path to your llamafile .exe: "
)
if not defined GGUF_MODEL (
    echo No GGUF model found in models\.
    set /p "GGUF_MODEL=Full path to your .gguf model file: "
)
if not defined LLAMAFILE_EXE goto aborted
if not defined GGUF_MODEL goto aborted
if not exist "%LLAMAFILE_EXE%" (
    echo Not found: %LLAMAFILE_EXE%
    set "LLAMAFILE_EXE="
    goto aborted
)
if not exist "%GGUF_MODEL%" (
    echo Not found: %GGUF_MODEL%
    set "GGUF_MODEL="
    goto aborted
)

if not exist "%~dp0local-paths.bat" (
    > "%~dp0local-paths.bat" echo set "LLAMAFILE_EXE=%LLAMAFILE_EXE%"
    >> "%~dp0local-paths.bat" echo set "GGUF_MODEL=%GGUF_MODEL%"
    echo Remembered these paths in local-paths.bat
)

rem --- Prerequisites ---
where uv >nul 2>&1 || goto no_uv
where node >nul 2>&1 || goto no_node

rem --- Launch three windows: backend, frontend, local model ---
echo Starting backend  (window 1, port 8000)...
start "IntrovertSOC backend"  /d "%~dp0backend"  cmd /k "uv run python manage.py runserver 127.0.0.1:8000"

echo Starting frontend (window 2, port 5173)...
start "IntrovertSOC frontend" /d "%~dp0frontend" cmd /k "npm run dev"

echo Starting local LLM (window 3, port 8080)...
netstat -ano | findstr /c:":8080 " | findstr LISTENING >nul 2>&1
if not errorlevel 1 (
    echo   port 8080 already has a model server - skipping llamafile
) else (
    start "IntrovertSOC LLM" cmd /k ""%LLAMAFILE_EXE%" -m "%GGUF_MODEL%" --server --host 127.0.0.1 --port 8080"
)

echo.
echo Waiting for the servers to come up...
timeout /t 6 /nobreak >nul
start "" http://127.0.0.1:5173

echo.
echo IntrovertSOC is starting. Three windows are open:
echo    1 backend   2 frontend   3 local model
echo Keep them open while you use it. Close them (or run stop.bat) to stop.
echo First login: the account you created in setup.bat.
pause
exit /b 0

:check
echo ==== IntrovertSOC launch check ====
if defined LLAMAFILE_EXE (echo llamafile : %LLAMAFILE_EXE%) else (echo llamafile : NOT FOUND)
if defined GGUF_MODEL    (echo model     : %GGUF_MODEL%)     else (echo model     : NOT FOUND)
where uv >nul 2>&1  && (echo uv        : OK) || (echo uv        : MISSING - run setup.bat)
where node >nul 2>&1 && (echo node      : OK) || (echo node      : MISSING - run setup.bat)
if exist "%~dp0backend\.venv" (echo backend deps : installed) else (echo backend deps : missing - run setup.bat)
if exist "%~dp0frontend\node_modules" (echo frontend deps: installed) else (echo frontend deps: missing - run setup.bat)
exit /b 0

:already_running
echo.
echo IntrovertSOC is already running (port 8000 or 5173 is busy).
echo Starting a second copy breaks logins and mode switching.
echo Use it as-is, or run stop.bat first and then start.bat again.
pause
exit /b 1

:aborted
echo Nothing launched.
pause
exit /b 1

:no_uv
echo [MISSING] uv - run setup.bat first.
pause
exit /b 1

:no_node
echo [MISSING] Node.js - run setup.bat first.
pause
exit /b 1
```

---

### 3. `stop.bat` (One-Click Shutdown)
Gracefully terminates processes bound to ports 8000 (backend), 5173 (frontend), and 8080 (llamafile), as well as any orphaned background worker processes.

```bat
@echo off
setlocal EnableExtensions
cd /d "%~dp0"

echo Stopping IntrovertSOC servers (ports 8000 backend, 5173 frontend, 8080 LLM)...

for %%P in (8000 5173 8080) do (
    for /f "tokens=5" %%I in ('netstat -ano ^| findstr /c:":%%P " ^| findstr LISTENING') do (
        echo   killing PID %%I on port %%P
        taskkill /f /pid %%I >nul 2>&1
    )
)

rem --- Orphaned dev processes (Django reloaders / extra vite or uv) ---
powershell -NoProfile -Command "Get-CimInstance Win32_Process | Where-Object { ($_.CommandLine -match 'manage\.py runserver' -and $_.CommandLine -match 'IntrovertSOC') -or ($_.CommandLine -match 'vite\.js' -and $_.CommandLine -match 'IntrovertSOC') -or ($_.Name -eq 'uv.exe' -and $_.CommandLine -match 'manage\.py runserver') } | ForEach-Object { Write-Host ('  killing orphan ' + $_.ProcessId + ' [' + $_.Name + ']'); Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }"

echo Done.
pause
```

---

### 4. `local-paths.bat` (Optional Path Override)
If your model or llamafile executable is stored on a different drive (e.g. `D:\LLMs\...`), create a file named `local-paths.bat` in the root folder with:

```bat
set "LLAMAFILE_EXE=D:\engineering\OFF_LLM\llamafile.exe"
set "GGUF_MODEL=D:\engineering\OFF_LLM\models\Qwen3-4B-Q4_K_M.gguf"
```
*(This file is automatically added to `.gitignore` so your personal directory paths are never pushed to GitHub).*

---

## 🚀 How to Use IntrovertSOC

1. **Start the Stack:**
   - Double-click `start.bat`. Three terminal windows will appear (Django Backend, Vite Frontend, and llamafile Server).
2. **Access the Web Console:**
   - Open your browser to `http://127.0.0.1:5173`.
   - Log in using the credentials created during `setup.bat`.
3. **Verify LLM Connection:**
   - Look at the top-right corner of the interface. The status indicator should turn **Green (Connected)**.
4. **Triage Alerts & Run Investigations:**
   - Navigate to **Alerts** or **Cases**.
   - Click on any incident to run automated AI triage, generate IOC extraction, and trigger playbooks.
5. **Switch Personas On the Fly:**
   - Use the top bar switch to toggle between **Work**, **Introvert**, and **Super Introvert** styles depending on your workload.
6. **Shutting Down:**
   - When finished, double-click `stop.bat` to release all ports and safely shut down all servers.

---

## 🔧 Troubleshooting & Common Issues

| Issue | Cause | Solution |
|---|---|---|
| **Port already in use error** | An existing background server is still occupying port 8000, 5173, or 8080. | Double-click `stop.bat` to terminate lingering processes, then run `start.bat` again. |
| **CSRF verification failed** | Multiple instances of Django are running simultaneously on port 8000. | Run `stop.bat`, close all open browser tabs for `127.0.0.1`, and re-launch `start.bat`. |
| **Status dot is Grey / Disconnected** | `llamafile` server is not running or model failed to load into RAM. | Check window 3 (LLM terminal) for error messages. Ensure your model fits in your available RAM. |
| **Empty or reasoning leakage in responses** | Model template outputting reasoning tokens into content. | IntrovertSOC's `local_engine.py` automatically handles reasoning filtering. Make sure you are using an Instruct GGUF model. |

---

## 📜 Attribution & License

IntrovertSOC is derived from [FunnyWolf/agentic-soc-platform](https://github.com/FunnyWolf/agentic-soc-platform) and licensed under the **MIT License**. See [LICENSE](LICENSE) for full legal text.
