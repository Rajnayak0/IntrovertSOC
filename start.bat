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
if not defined LLAMAFILE_EXE if exist "D:\engineering\OFF_LLM\llamafile.exe" set "LLAMAFILE_EXE=D:\engineering\OFF_LLM\llamafile.exe"
if not defined LLAMAFILE_EXE if exist "D:\engineering\OFF_LLM\llamafile-0.10.6.exe" set "LLAMAFILE_EXE=D:\engineering\OFF_LLM\llamafile-0.10.6.exe"
if not defined LLAMAFILE_EXE if defined LLAMAFILE set "LLAMAFILE_EXE=%LLAMAFILE%"

rem --- Auto-detect the first .gguf in models\ ---
if not defined GGUF_MODEL for %%F in ("%~dp0models\*.gguf") do if not defined GGUF_MODEL set "GGUF_MODEL=%%~fF"
if not defined GGUF_MODEL if defined LLAMAFILE_MODEL_PATH set "GGUF_MODEL=%LLAMAFILE_MODEL_PATH%"

rem --- check mode: print detection status, launch nothing ---
if /i "%~1"=="check" goto check

rem --- Refuse to start a second stack: two backends on one port cause
rem --- session/CSRF mixups ("CSRF token ... incorrect" errors) ---
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
