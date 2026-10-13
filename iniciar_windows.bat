@echo off
chcp 65001 > nul
echo =======================================================
echo   FINART S.A.S. · Dashboard ARDP Falabella
echo =======================================================
echo Iniciando servidor Streamlit...

if exist venv\Scripts\activate.bat (
    call venv\Scripts\activate.bat
) else if exist .venv\Scripts\activate.bat (
    call .venv\Scripts\activate.bat
)

python -m streamlit run app.py
pause
