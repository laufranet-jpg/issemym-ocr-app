@echo off
title ISSEMYM - Servidor Local
cd /d %~dp0
call venv\Scripts\activate

REM Obtiene la IP local (primera IPv4 que aparece en ipconfig)
for /f "tokens=2 delims=:" %%a in ('ipconfig ^| findstr /i "IPv4"') do (
    set IP=%%a
    goto :found
)
:found
set IP=%IP: =%

echo.
echo  ============================================================
echo    ISSEMYM - Sistema de Gestion Documental
echo    Secretaria de Educacion del Estado de Mexico
echo  ============================================================
echo.
echo    Servidor iniciado correctamente.
echo.
echo    Accede desde ESTA computadora:
echo    ^> http://127.0.0.1:8000
echo.
echo    Accede desde CUALQUIER PC de la red de oficina:
echo    ^> http://%IP%:8000
echo.
echo    Usuario admin: admin
echo    Contrasena:    Admin@2026!  (cambiala al entrar)
echo.
echo    Para DETENER el servidor presiona Ctrl+C
echo  ============================================================
echo.

python -m uvicorn app.main:app --host 0.0.0.0 --port 8000

pause
