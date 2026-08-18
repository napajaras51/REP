@echo off
setlocal
cd /d "%~dp0"

where python >nul 2>nul
if errorlevel 1 (
  echo Python was not found. Install Python 3.10 or newer and try again.
  pause
  exit /b 1
)

python -c "import fastapi, uvicorn, jinja2, multipart" >nul 2>nul
if errorlevel 1 (
  echo Required packages are missing.
  echo Run: python -m pip install -r requirements.txt
  pause
  exit /b 1
)

python "%~dp0run_webapp.py"
if errorlevel 1 pause
