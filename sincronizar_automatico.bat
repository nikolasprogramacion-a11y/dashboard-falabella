@echo off
REM Corre sync.py y deja un registro en sync_log.txt con fecha y hora.
REM No cierres esta ventana sola: el Programador de tareas la abre y la cierra solo.
cd /d "%~dp0"
echo ==== %date% %time% ==== >> sync_log.txt

REM El Programador de tareas a veces no encuentra "python" aunque en tu
REM terminal normal sí funcione. Se intenta primero con "py" (el lanzador
REM oficial de Windows, casi siempre disponible), y si falla, con "python".
where py >nul 2>&1
if %errorlevel%==0 (
    py sync.py >> sync_log.txt 2>&1
) else (
    python sync.py >> sync_log.txt 2>&1
)
echo. >> sync_log.txt
