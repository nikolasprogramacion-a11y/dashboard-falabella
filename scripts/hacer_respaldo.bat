@echo off
chcp 65001 > nul
cd /d "%~dp0\.."
echo Ejecutando respaldo de seguridad...
python scripts\backup.py
pause
