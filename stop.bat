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
