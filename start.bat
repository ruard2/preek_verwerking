@echo off
setlocal
cd /d "%~dp0"
title Preekverwerker

echo ================================================
echo   Preekverwerker - lokaal starten
echo ================================================
echo.

REM --- 1. Eenmalig: controleren of er een .env is met de OpenAI-sleutel ---
if not exist ".env" (
    echo LET OP: er is nog geen .env-bestand.
    echo Kopieer .env.example naar .env en vul je OPENAI_API_KEY in.
    echo.
    pause
    exit /b 1
)

REM --- 2. Python-pakketten installeren (eerste keer; daarna vrijwel instant) ---
echo Pakketten controleren/installeren...
python -m pip install -q -r requirements.txt

REM --- 3. PO-token-provider starten (voor de audio-transcriptie) ---
echo Token-provider starten...
docker info >nul 2>&1
if errorlevel 1 (
    echo   Docker draait nog niet; Docker Desktop wordt gestart...
    start "" "C:\Program Files\Docker\Docker\Docker Desktop.exe"
    echo   Even wachten tot Docker klaar is...
    powershell -NoProfile -Command "$n=0; while($n -lt 60){ docker info *> $null; if($?){break}; Start-Sleep 2; $n+=2 }"
)
docker start bgutil-pot >nul 2>&1 || docker run -d --name bgutil-pot -p 4416:4416 brainicism/bgutil-ytdlp-pot-provider >nul 2>&1
if errorlevel 1 (
    echo   Kon de token-provider niet starten. De app werkt dan met
    echo   ondertitels in plaats van audio-transcriptie.
)

REM --- 4. Browser openen en de app starten ---
echo.
echo De app start op http://127.0.0.1:8123
echo Sluit dit venster om de app te stoppen.
echo.
start "" "http://127.0.0.1:8123"
python -m uvicorn main:app --host 127.0.0.1 --port 8123

endlocal
