@echo off
setlocal
cd /d "%~dp0"

if exist "%~dp0.runtime\python.exe" (
    "%~dp0.runtime\python.exe" -X utf8 "%~dp0launch.py"
    goto :finished
)

if exist "%~dp0runtime\python.exe" (
    "%~dp0runtime\python.exe" -X utf8 "%~dp0launch.py"
    goto :finished
)

if exist "%~dp0.venv\Scripts\python.exe" (
    "%~dp0.venv\Scripts\python.exe" -X utf8 "%~dp0launch.py"
    goto :finished
)

where py >nul 2>&1
if not errorlevel 1 (
    py -3 -X utf8 "%~dp0launch.py"
    goto :finished
)

where python >nul 2>&1
if not errorlevel 1 (
    python -X utf8 "%~dp0launch.py"
    goto :finished
)

echo.
echo Python was not found. Please prepare .runtime or install Python first.
pause
exit /b 1

:finished
if errorlevel 1 (
    echo.
    echo Startup failed. See the message above or check the run log.
    pause
    exit /b 1
)

endlocal
