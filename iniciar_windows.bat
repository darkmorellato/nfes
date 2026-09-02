@echo off
chcp 65001 > nul
title NFE Manager — Inicializador Windows
color 0A

echo ===============================================================================
echo                   🏛️  NFE MANAGER — SISTEMA FISCAL SEFAZ
echo ===============================================================================
echo.

:: 1. Verifica se o Python está instalado
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERRO] Python não foi encontrado no seu computador!
    echo.
    echo Por favor, baixe e instale o Python em: https://www.python.org/downloads/
    echo.
    echo ATENÇÃO: Durante a instalação, marque a caixinha "Add Python to PATH" ou
    echo "Adicionar Python às variáveis de ambiente".
    echo.
    pause
    exit /b 1
)

echo [1/3] Python detectado com sucesso!

:: 2. Cria o ambiente virtual venv se não existir
if not exist "venv\Scripts\activate.bat" (
    echo [2/3] Criando ambiente virtual isolado (venv)...
    python -m venv venv
    if %errorlevel% neq 0 (
        echo [ERRO] Falha ao criar o ambiente virtual venv.
        pause
        exit /b 1
    )
    echo [2/3] Instalando dependências do sistema (aguarde alguns instantes)...
    call venv\Scripts\activate.bat
    python -m pip install --upgrade pip
    pip install -r backend/requirements.txt
) else (
    echo [2/3] Ambiente virtual pronto!
    call venv\Scripts\activate.bat
)

:: 3. Inicia o servidor e abre o navegador automaticamente
echo [3/3] Iniciando o NFE Manager...
echo.
echo ===============================================================================
echo   O sistema abrirá automaticamente no seu navegador em: http://127.0.0.1:8000
echo   Para encerrar o sistema, basta fechar esta janela preta.
echo ===============================================================================
echo.

set PYTHONPATH=.
python app_launcher.py

pause
