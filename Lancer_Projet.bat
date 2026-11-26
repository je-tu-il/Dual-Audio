@echo off
setlocal DisableDelayedExpansion
set "APP_PAGE=%~dp0pages\index.html"

if not exist "%APP_PAGE%" (
    echo [ERREUR] Page de Dual Audio Web introuvable.
    echo "%APP_PAGE%"
    pause
    exit /b 1
)

start "" "%APP_PAGE%"
if errorlevel 1 (
    echo [ERREUR] Impossible d'ouvrir Dual Audio Web. Ouvrez cette page dans votre navigateur :
    echo "%APP_PAGE%"
    pause
    exit /b 1
)

exit /b 0
