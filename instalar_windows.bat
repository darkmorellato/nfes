@echo off
chcp 65001 > nul
title NFE Manager — Instalador Automático Windows (1-Clique)
color 0B

echo ===============================================================================
echo                 🏛️  NFE MANAGER — INSTALADOR AUTOMÁTICO WINDOWS
echo ===============================================================================
echo.
echo Este assistente irá configurar o NFE Manager no seu computador automaticamente.
echo.

:: 1. Verifica se o Python está instalado
echo [1/4] Verificando instalação do Python...
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo.
    echo ❌ [ERRO] Python não foi encontrado no seu sistema!
    echo.
    echo 📥 Como resolver em 2 minutos:
    echo 1. Acesse o site oficial: https://www.python.org/downloads/
    echo 2. Baixe o instalador do Python 3 (recomendado 3.10 ou superior)
    echo 3. IMPORTANTE: Na primeira tela da instalação, marque a caixinha:
    echo    [X] "Add Python to PATH" ou "Adicionar Python às variáveis de ambiente"
    echo 4. Conclua a instalação e dê dois cliques neste arquivo novamente.
    echo.
    pause
    exit /b 1
)

for /f "tokens=*" %%i in ('python --version') do set PYTHON_VER=%%i
echo ✅ [1/4] %PYTHON_VER% detectado com sucesso!
echo.

:: 2. Cria ambiente virtual isolado (venv)
echo [2/4] Criando ambiente virtual isolado (venv)...
if not exist "venv\Scripts\activate.bat" (
    python -m venv venv
    if %errorlevel% neq 0 (
        echo.
        echo ❌ [ERRO] Falha ao criar ambiente virtual venv.
        pause
        exit /b 1
    )
    echo ✅ Ambiente virtual criado com sucesso!
) else (
    echo ℹ️ Ambiente virtual já existe, prosseguindo...
)
echo.

:: 3. Instala dependências do Python
echo [3/4] Instalando dependências e pacotes fiscais (pode levar 1 a 2 minutos)...
call venv\Scripts\activate.bat
python -m pip install --upgrade pip -q
pip install -r backend/requirements.txt
if %errorlevel% neq 0 (
    echo.
    echo ❌ [ERRO] Falha ao instalar dependências. Verifique sua conexão com a internet.
    pause
    exit /b 1
)
echo ✅ [3/4] Dependências instaladas com sucesso!
echo.

:: 4. Configuração inicial do .env
echo [4/4] Verificando arquivos de configuração...
if not exist ".env" (
    if exist ".env.example" (
        copy ".env.example" ".env" >nul
        echo ✅ Arquivo de configuração .env criado a partir do modelo padrão.
    )
)
echo ✅ [4/4] Configurações prontas!
echo.

echo ===============================================================================
echo                 🎉 INSTALAÇÃO CONCLUÍDA COM SUCESSO!
echo ===============================================================================
echo.
echo Para abrir o NFE Manager no seu computador a qualquer momento:
echo 👉 Dê dois cliques no arquivo: iniciar_windows.bat
echo.
echo Deseja iniciar o sistema agora? (S/N)
set /p START_NOW="Digite S para Sim ou N para Não: "

if /i "%START_NOW%"=="S" (
    echo.
    echo 🚀 Iniciando o sistema...
    start iniciar_windows.bat
)

echo.
pause
