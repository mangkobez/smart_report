@echo off
cd /d "%~dp0"
set PYTHONIOENCODING=utf-8

echo Memeriksa Streamlit...
.venv\Scripts\python -c "import streamlit" 2>nul
if errorlevel 1 (
    echo Streamlit belum terinstall, sedang install...
    .venv\Scripts\pip install streamlit
)

echo.
echo ============================================
echo   SmartReport Editor
echo   Membuka browser dalam beberapa detik...
echo   Tutup jendela ini untuk menghentikan.
echo ============================================
echo.

.venv\Scripts\streamlit run editor.py --server.port 8501 --browser.gatherUsageStats false
pause
