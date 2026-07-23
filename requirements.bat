@echo off
cd /d "%~dp0"

set "VENV_PY=.venv\Scripts\python.exe"
set "PYTHON_CMD="

if not exist "%VENV_PY%" (

    where python >nul 2>nul
    if not errorlevel 1 (
        set "PYTHON_CMD=python"
        goto crear_venv
    )

    where py >nul 2>nul
    if not errorlevel 1 (
        set "PYTHON_CMD=py -3"
        goto crear_venv
    )

    echo No se encontro Python 3.
    echo.
    echo Soluciones:
    echo 1. Instala Python desde https://www.python.org/downloads/
    echo 2. Marca la opcion "Add Python to PATH"
    echo 3. Cierra y abre nuevamente CMD
    echo.
    pause
    exit /b 1
)

goto instalar

:crear_venv
echo Usando: %PYTHON_CMD%
echo Creando entorno virtual en .venv ...

%PYTHON_CMD% -m venv .venv

if errorlevel 1 (
    echo No se pudo crear .venv.
    pause
    exit /b 1
)

:instalar
"%VENV_PY%" -m pip install --upgrade pip
if errorlevel 1 exit /b %ERRORLEVEL%

"%VENV_PY%" -m pip install -r requirements.txt
if errorlevel 1 exit /b %ERRORLEVEL%

echo.
echo Dependencias instaladas correctamente.
pause