@echo off
setlocal

echo ============================================================
echo  Genesis Studio -- Start AI Server
echo  Model: genesis-llm (Llama 3.1 70B)
echo  RTX 5090: 24GB VRAM + system RAM offload
echo ============================================================
echo.

:: Allow Ollama to use all GPU layers it can fit, offload rest to CPU
set OLLAMA_NUM_GPU=999
set OLLAMA_HOST=127.0.0.1:11434
set OLLAMA_FLASH_ATTENTION=1

:: Check if already running
ollama list >nul 2>&1
if not errorlevel 1 (
    echo Ollama already running -- verifying model...
    goto :run_model
)

echo Starting Ollama server...
start /min "Ollama Server" ollama serve
echo Waiting for server to start...
timeout /t 4 /nobreak >nul

:run_model
:: Check model exists
ollama list | findstr /i "genesis-llm" >nul 2>&1
if errorlevel 1 (
    echo.
    echo ERROR: genesis-llm not found.
    echo Run setup_llm.bat first to import the model.
    echo.
    pause
    exit /b 1
)

echo.
echo Warming up genesis-llm on GPU...
echo (First load may take 30-60 seconds as layers load into VRAM)
echo.

:: Keep model hot in memory with a keep-alive ping
ollama run genesis-llm --keepalive 24h "Ready." 2>&1 | findstr /v "^$"

echo.
echo ============================================================
echo  AI Server is LIVE at http://localhost:11434
echo  Model: genesis-llm loaded and warm
echo  Press Ctrl+C in the Ollama window to stop
echo ============================================================
echo.
echo You can now click "Create Video" in Genesis Studio with
echo "Use local LLM" toggled ON.
echo.
pause
