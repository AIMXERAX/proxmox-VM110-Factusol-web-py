@echo off
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" exit /b 1

".venv\Scripts\python.exe" "factusol_web_service.py" stop
".venv\Scripts\python.exe" "factusol_web_service.py" remove
