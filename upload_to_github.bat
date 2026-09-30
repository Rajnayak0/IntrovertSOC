@echo off
setlocal EnableExtensions
cd /d "%~dp0"
title Upload to GitHub - IntrovertSOC

echo ========================================================
echo   IntrovertSOC - Push to GitHub (Rajnayak0/IntrovertSOC)
echo ========================================================
echo.
echo Step 1: Make sure you created the empty repo on GitHub:
echo         https://github.com/new (Name: IntrovertSOC)
echo.
echo Step 2: Press any key to push your code...
pause >nul
echo.
echo Pushing main branch to origin...
git push -u origin main

if errorlevel 1 (
    echo.
    echo ========================================================
    echo  Push failed! Check the following:
    echo  1. Did you create the repo at https://github.com/new
    echo     with the exact name "IntrovertSOC"?
    echo  2. If GitHub prompts for login in your browser, approve it.
    echo ========================================================
) else (
    echo.
    echo ========================================================
    echo  SUCCESS! Your code is live on GitHub:
    echo  https://github.com/Rajnayak0/IntrovertSOC
    echo ========================================================
)
echo.
pause
