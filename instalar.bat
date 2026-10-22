@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo Instalando o Raio-X do Disco (só cria o ambiente Python; não baixa nada)...
if not exist ".venv\Scripts\pythonw.exe" (
    python -m venv .venv || goto erro
)
echo.
echo Pronto. Abra pelo atalho do Menu Iniciar ou com: .venv\Scripts\pythonw.exe iniciar.pyw
pause
exit /b 0
:erro
echo.
echo A instalacao parou com erro. Veja a mensagem acima.
pause
exit /b 1
