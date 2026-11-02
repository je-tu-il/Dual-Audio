@echo off
chcp 65001 >nul
title Compilation Standalone EXE - Dual-Audio
cd /d "%~dp0"

echo ========================================================
echo   Compilation EXE Standalone — Dual-Audio
echo ========================================================
echo.

set "PY_BIN=%~dp0venv\Scripts\python.exe"
if not exist "%PY_BIN%" set "PY_BIN=python"

echo [*] Verification et installation de PyInstaller...
"%PY_BIN%" -m pip install -q pyinstaller

echo [*] Compilation du fichier executable unique (sans fenetre console)...
"%PY_BIN%" -m PyInstaller --noconsole --onefile ^
    --name="Dual-Audio" ^
    --collect-all customtkinter ^
    --collect-all pygame ^
    --hidden-import=audioop_lts ^
    --clean ^
    main.py

if errorlevel 1 (
    echo.
    echo [ERREUR] La compilation a echoue.
    pause
    exit /b 1
)

if exist "dist\Dual-Audio.exe" (
    copy /y "dist\Dual-Audio.exe" "%~dp0Dual-Audio.exe" >nul
    echo.
    echo ========================================================
    echo   [SUCCES] Executable genere : Dual-Audio.exe
    echo ========================================================
)

echo.
pause
