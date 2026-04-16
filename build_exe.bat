@echo off
REM build_exe.bat — Gera IPL-APS.exe no Windows
REM Uso: Duplo-clique ou execute no PowerShell/CMD
setlocal enabledelayedexpansion

echo === IPL-APS Build (Windows) ===
cd /d "%~dp0"

REM ── Verifica Python ────────────────────────────────────────────────────
python --version >nul 2>&1
if errorlevel 1 (
    echo ERRO: Python nao encontrado.
    echo Instale em https://www.python.org/downloads/ e marque "Add to PATH"
    pause
    exit /b 1
)

REM ── Ativa venv se existir ──────────────────────────────────────────────
if exist "venv\Scripts\activate.bat" (
    call venv\Scripts\activate.bat
    echo [OK] venv ativado
) else (
    echo Criando venv...
    python -m venv venv
    call venv\Scripts\activate.bat
)

REM ── Instala dependências ───────────────────────────────────────────────
echo Instalando dependencias...
pip install -r requirements.txt --quiet
pip install pyinstaller --quiet

REM ── Limpa builds anteriores ────────────────────────────────────────────
if exist build rmdir /s /q build
if exist dist  rmdir /s /q dist
echo [OK] Build anterior removido

REM ── Gera executável ────────────────────────────────────────────────────
echo Gerando executavel (pode levar 3-6 minutos)...
pyinstaller ipl_aps.spec --noconfirm
if errorlevel 1 (
    echo ERRO: Falha no PyInstaller
    pause
    exit /b 1
)

REM ── Cria pasta de dados ────────────────────────────────────────────────
mkdir dist\IPL-APS\data 2>nul

REM ── Copia arquivos extras ──────────────────────────────────────────────
if exist ".env.example"              copy ".env.example"              "dist\IPL-APS\" >nul
if exist "valores_referencia.sql"    copy "valores_referencia.sql"    "dist\IPL-APS\" >nul
if exist "IPL_SCORE_METODOLOGIA.md"  copy "IPL_SCORE_METODOLOGIA.md"  "dist\IPL-APS\" >nul

REM ── LEIA-ME ────────────────────────────────────────────────────────────
(
echo IPL-APS - Sistema Municipal de Prioridade Laboratorial
echo =======================================================
echo.
echo PRIMEIRO USO
echo ------------
echo 1. Execute IPL-APS.exe
echo 2. Preencha o assistente de configuracao
echo 3. Acesse http://localhost:8080
echo.
echo REQUISITOS OPCIONAIS
echo --------------------
echo Tesseract OCR ^(PDFs sem texto^):
echo   https://github.com/UB-Mannheim/tesseract/wiki
echo.
echo Secretaria Municipal de Saude - Suzano/SP
) > dist\IPL-APS\LEIA-ME.txt

REM ── Compacta ───────────────────────────────────────────────────────────
powershell -Command "Compress-Archive -Path 'dist\IPL-APS' -DestinationPath 'dist\IPL-APS-windows.zip' -Force"

echo.
echo ==============================================
echo  Build concluido!
echo  Executavel: dist\IPL-APS\IPL-APS.exe
echo  Pacote:     dist\IPL-APS-windows.zip
echo ==============================================
echo.
pause
