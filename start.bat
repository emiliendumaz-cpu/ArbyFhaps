@echo off
title ArbyFhaps - Bot Discord Arbitration
cd /d "%~dp0"

where python >nul 2>nul
if errorlevel 1 (
    echo [ERREUR] Python est introuvable. Installez-le depuis https://www.python.org/downloads/
    echo et cochez "Add Python to PATH" pendant l'installation.
    pause
    exit /b 1
)

if not exist ".env" (
    echo [ERREUR] Fichier .env manquant.
    echo Copiez .env.example vers .env puis renseignez votre DISCORD_TOKEN.
    pause
    exit /b 1
)

if not exist ".venv\Scripts\python.exe" (
    echo Premiere utilisation : creation de l'environnement Python...
    python -m venv .venv
)

echo Verification des dependances...
".venv\Scripts\python.exe" -m pip install -q -r requirements.txt

echo.
echo Lancement du bot... ^(Ctrl+C ou fermez cette fenetre pour l'arreter^)
echo.
".venv\Scripts\python.exe" bot.py

echo.
echo Le bot s'est arrete.
pause
