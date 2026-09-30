@echo off
setlocal
cd /d "%~dp0"

where py >nul 2>&1
if %errorlevel% equ 0 (
  py -3 brief_reader.py --open
) else (
  python brief_reader.py --open
)

if errorlevel 1 (
  echo Reader failed. Install Python 3.10 or newer and try again.
  pause
)
