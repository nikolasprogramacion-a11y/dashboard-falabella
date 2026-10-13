@echo off
REM ==============================================================================
REM  FINART S.A.S. · Tarea programada de sincronización con Falabella Seller Center
REM  Compatible con Programador de Tareas de Windows (Task Scheduler)
REM ==============================================================================
setlocal EnableDelayedExpansion
cd /d "%~dp0\.."

if not exist "logs" mkdir "logs"
set LOG_FILE=logs\sync.log

echo =================================================== >> %LOG_FILE%
echo [%date% %time%] Iniciando sincronización... >> %LOG_FILE%

set PYTHON_CMD=
where py >nul 2>&1
if %errorlevel%==0 (
    set PYTHON_CMD=py
) else (
    where python >nul 2>&1
    if %errorlevel%==0 (
        set PYTHON_CMD=python
    )
)

if "%PYTHON_CMD%"=="" (
    echo [ERROR] No se encontró el ejecutable de Python o Py en PATH. >> %LOG_FILE%
    exit /b 1
)

%PYTHON_CMD% sync.py >> %LOG_FILE% 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Falló la ejecución de sync.py con código de salida %errorlevel%. >> %LOG_FILE%
) else (
    echo [%date% %time%] Sincronización finalizada exitosamente. >> %LOG_FILE%
)
echo. >> %LOG_FILE%
