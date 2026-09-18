@echo off
cd /d "%~dp0"
set PYTHONIOENCODING=utf-8
.venv\Scripts\python -u bot.py >> logs\bot.log 2>&1
