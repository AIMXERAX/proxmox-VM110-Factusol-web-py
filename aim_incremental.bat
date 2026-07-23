@echo off
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    if exist "requirements.bat" (
        call "requirements.bat"
    ) else (
        echo No se encontro .venv\Scripts\python.exe.
        echo Ejecuta requirements.bat para crear el entorno virtual.
        exit /b 1
    )
)

if not exist ".venv\Scripts\python.exe" (
    echo No se pudo preparar el entorno virtual.
    exit /b 1
)

".venv\Scripts\python.exe" "aim_datos_accdb_incremental.py" --name=incremental_simple %*
exit /b %ERRORLEVEL%
