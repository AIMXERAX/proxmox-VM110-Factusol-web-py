@echo off
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" call "requirements.bat"
if not exist ".venv\Scripts\python.exe" exit /b 1

net session >nul 2>&1
if errorlevel 1 (
    echo ERROR: Este comando debe ejecutarse como administrador.
    exit /b 1
)

echo Instalando el servicio como administrador.
".venv\Scripts\python.exe" ".venv\Scripts\pywin32_postinstall.py" -install
if errorlevel 1 exit /b %ERRORLEVEL%

".venv\Scripts\python.exe" "factusol_web_service.py" --startup auto install
if errorlevel 1 exit /b %ERRORLEVEL%

copy /Y ".venv\Lib\site-packages\pywin32_system32\pywintypes*.dll" ".venv\" >nul
if errorlevel 1 exit /b %ERRORLEVEL%
copy /Y ".venv\Lib\site-packages\pywin32_system32\pythoncom*.dll" ".venv\" >nul
if errorlevel 1 exit /b %ERRORLEVEL%
set "PYTHON_RUNTIME_DIR=%LOCALAPPDATA%\Python\pythoncore-3.14-64"
if not exist "%PYTHON_RUNTIME_DIR%\python314.dll" (
    echo ERROR: No se encontro python314.dll en "%PYTHON_RUNTIME_DIR%".
    exit /b 1
)
copy /Y "%PYTHON_RUNTIME_DIR%\python314.dll" ".venv\" >nul
if errorlevel 1 exit /b %ERRORLEVEL%
copy /Y "%PYTHON_RUNTIME_DIR%\python3.dll" ".venv\" >nul
if errorlevel 1 exit /b %ERRORLEVEL%

sc failure "AIMXERAX_FACTUSOL_WEB" reset= 86400 actions= restart/60000/restart/60000/restart/60000

".venv\Scripts\python.exe" "factusol_web_service.py" start
exit /b %ERRORLEVEL%
