@echo off
REM Windows: double-click to start retrace. Checks for Python 3 and guides if missing.
cd /d "%~dp0"

where py >nul 2>nul
if %errorlevel%==0 ( py server.py --port 8787 & goto :done )
where python >nul 2>nul
if %errorlevel%==0 ( python server.py --port 8787 & goto :done )

echo.
echo   retrace needs Python 3 - it isn't installed on this PC yet.
echo.
echo   Easiest fix (do this once):
echo     1. Open PowerShell and run:
echo          winget install -e --id Python.Python.3.12
echo     2. Close and reopen this window, then double-click start-retrace.bat again.
echo.
echo   Prefer a download? Get it here, and CHECK "Add python.exe to PATH":
echo          https://www.python.org/downloads/
echo.
pause
goto :eof

:done
echo retrace is running - open http://127.0.0.1:8787 in your browser.
pause
