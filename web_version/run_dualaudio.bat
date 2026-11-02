@echo off
title DualAudio - Routage Audio par Oreille
cd /d "%~dp0"

echo ========================================================
echo       DualAudio - Routage Audio pour Casque
echo ========================================================
echo.
echo Lancement en cours...
python app.py %*

if %ERRORLEVEL% NEQ 0 (
    echo.
    echo [ERREUR] Le lancement a echoue.
    pause
)
