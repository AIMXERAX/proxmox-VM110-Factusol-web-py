@echo off
cd /d "%~dp0"

REM ========================================================================
REM Script de reconstruccion de estructura de base de datos
REM ========================================================================

title Reconstruccion de Estructura BD Factusol

if not exist ".venv\Scripts\python.exe" (
    if exist "requirements.bat" (
        call "requirements.bat"
    ) else (
        echo No se encontro .venv\Scripts\python.exe.
        echo Ejecuta requirements.bat para crear el entorno virtual.
        pause
        exit /b 1
    )
)

if not exist ".venv\Scripts\python.exe" (
    echo No se pudo preparar el entorno virtual.
    pause
    exit /b 1
)

echo.
echo ========================================================================
echo          RECONSTRUCCION DE ESTRUCTURA DE BASE DE DATOS
echo ========================================================================
echo.
echo PROCESO AUTOMATICO - Iniciando en 5 segundos...
echo.
echo Este proceso reconstruira completamente las tablas MySQL:
echo   - DROP todas las tablas existentes
echo   - CREATE tablas con estructura actualizada
echo   - Recarga todos los datos desde Access
echo.
echo IMPORTANTE: Asegurese de que Factusol NO este en uso
echo             Este proceso puede tardar 10-30 minutos
echo.
echo ========================================================================
echo.

timeout /t 5 /nobreak > nul

".venv\Scripts\python.exe" "reconstruir_estructura_bd.py" --name=reconstruccion %*

if errorlevel 1 (
    echo.
    echo ========================================================================
    echo                  PROCESO COMPLETADO CON ERRORES
    echo ========================================================================
    echo.
    echo Revise el log: logs\monitor.log
    echo.
    pause
) else (
    echo.
    echo ========================================================================
    echo                  PROCESO COMPLETADO EXITOSAMENTE
    echo ========================================================================
    echo.
)
pause
