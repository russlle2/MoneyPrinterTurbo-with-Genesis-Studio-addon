@echo off
setlocal

echo ============================================================
echo  Genesis Studio -- LLM Setup
echo  Importing your Llama 3.1 70B model into Ollama
echo ============================================================
echo.

:: Check Ollama is available
where ollama >nul 2>&1
if errorlevel 1 (
    echo ERROR: Ollama not found in PATH.
    echo Download from https://ollama.com and install, then re-run this.
    pause
    exit /b 1
)

echo Ollama found. Starting server in background...
start /min "Ollama Server" ollama serve
timeout /t 3 /nobreak >nul

echo.
echo Importing model (this converts your safetensors to GGUF Q4_K_M).
echo This will take 20-60 minutes the FIRST time only.
echo The converted model will be ~40GB stored in C:\Users\%USERNAME%\.ollama\models
echo.
echo DO NOT close this window until it says "success".
echo.

cd /d "%~dp0"
ollama create genesis-llm -f Modelfile

if errorlevel 1 (
    echo.
    echo ERROR: Model import failed. See message above.
    pause
    exit /b 1
)

echo.
echo ============================================================
echo  SUCCESS -- Model imported as "genesis-llm"
echo ============================================================
echo.
echo Genesis Studio is already configured to use it.
echo To start the AI server, run:  start_llm.bat
echo.
pause
