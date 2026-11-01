@echo off
REM Gera o EasyServ e o instalador (dist\EasyServ_Setup_<versao>.exe + .sha256).
REM Passo a passo completo (inclusive como publicar no GitHub): ferramentas\COMO_PUBLICAR.txt
cd /d "%~dp0"
python -m pip install -r requirements.txt
python ferramentas\gerar_instalador.py
echo.
pause
