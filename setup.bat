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
