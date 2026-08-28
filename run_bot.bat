@echo off
cd /d "E:\Projects\Kapus\SmartReport"
set PYTHONIOENCODING=utf-8
.venv\Scripts\python -u bot.py >> logs\bot.log 2>&1
