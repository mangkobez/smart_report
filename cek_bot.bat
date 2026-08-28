@echo off
echo ========================================
echo  SMARTREPORT BOT - Status
echo ========================================

tasklist /fi "imagename eq python.exe" | find "python.exe" >nul
if %errorlevel% == 0 (
    echo  STATUS : BERJALAN
) else (
    echo  STATUS : TIDAK AKTIF
)

echo.
echo --- Log terakhir ---
powershell -command "if (Test-Path 'logs\bot.log') { Get-Content 'logs\bot.log' -Tail 5 } else { Write-Host 'Log belum ada.' }"
echo.
pause
