@echo off
setlocal DisableDelayedExpansion
where.exe node.exe >nul 2>&1
if errorlevel 1 (
    echo [ERREUR] Node.js est necessaire pour lancer les tests.
    exit /b 1
)
node.exe --test "%~dp0tests\web-audio.test.cjs"
exit /b %errorlevel%
