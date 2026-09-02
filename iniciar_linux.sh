#!/usr/bin/env bash
# ==============================================================================
# NFE Manager — Inicializador Automático para Linux (1 Clique)
# Compatível com Ubuntu, Debian, Arch Linux, Fedora, Mint, Zorin, etc.
# ==============================================================================

set -e
cd "$(dirname "$0")"

echo "==============================================================================="
echo "                  🏛️  NFE MANAGER — SISTEMA FISCAL SEFAZ"
echo "==============================================================================="
echo ""

# 1. Verifica se o Python 3 está instalado
if ! command -v python3 &>/dev/null; then
    echo "❌ [ERRO] Python 3 não encontrado no seu sistema."
    echo "Execute: sudo apt install python3 python3-venv (ou sudo pacman -S python)"
    echo "Ou execute o script: ./instalar_dependencias.sh"
    exit 1
fi

echo "✅ [1/3] Python 3 detectado!"

# 2. Cria ambiente virtual venv se não existir
if [ ! -f "venv/bin/activate" ]; then
    echo "⚙️ [2/3] Criando ambiente virtual isolado (venv)..."
    python3 -m venv venv || {
        echo "❌ Falha ao criar venv. No Ubuntu/Debian, instale: sudo apt install python3-venv"
        exit 1
    }
    echo "📦 [2/3] Instalando dependências (aguarde alguns instantes)..."
    ./venv/bin/pip install --upgrade pip
    ./venv/bin/pip install -r backend/requirements.txt
else
    echo "✅ [2/3] Ambiente virtual pronto!"
fi

# 3. Inicia a aplicação
echo "🚀 [3/3] Iniciando o NFE Manager..."
echo ""
echo "==============================================================================="
echo "  O sistema abrirá automaticamente no seu navegador em: http://127.0.0.1:8000"
echo "  Para encerrar o sistema, pressione Ctrl + C neste terminal."
echo "==============================================================================="
echo ""

export PYTHONPATH=.
./venv/bin/python app_launcher.py
