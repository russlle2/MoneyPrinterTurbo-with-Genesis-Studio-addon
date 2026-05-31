@echo off
setlocal

echo ============================================================
echo  Genesis Forge
echo  Video generation from text, images, or both
echo ============================================================
echo.

where streamlit >nul 2>&1
if errorlevel 1 (
    echo Installing Streamlit...
    pip install streamlit --quiet
)

cd /d "%~dp0"

echo Starting Genesis Forge...
echo.
echo  The UI will open at: http://localhost:8502
echo.
echo  Close this window to stop the server.
echo.

streamlit run genesis/ui/video_forge_ui.py ^
    --server.port 8502 ^
    --server.headless false ^
    --browser.gatherUsageStats false ^
    --theme.base dark ^
    --theme.primaryColor "#e63946" ^
    --theme.backgroundColor "#0d0d0d" ^
    --theme.secondaryBackgroundColor "#1a1a1a" ^
    --theme.textColor "#f0f0f0"
