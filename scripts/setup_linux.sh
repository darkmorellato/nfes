#!/bin/bash
set -e

echo "=== Instalacao de dependencias para NFE Manager ==="
echo "Distribuicao: $(cat /etc/os-release 2>/dev/null | grep PRETTY_NAME | cut -d= -f2 | tr -d '\"')"
echo ""

if command -v apt-get &> /dev/null; then
    echo "[*] Usando apt-get (Ubuntu/Zorin)"
    sudo apt-get update
    sudo apt-get install -y python3 python3-pip python3-venv python3-dev \
        libssl-dev libffi-dev libxml2-dev libxslt1-dev \
        openssl p11-kit p11-kit-modules \
        build-essential libjpeg-dev zlib1g-dev
elif command -v pacman &> /dev/null; then
    echo "[*] Usando pacman (CachyOS/Arch)"
    sudo pacman -Sy --noconfirm python python-pip base-devel \
        openssl libffi libxml2 libxslt p11-kit
else
    echo "[!] Gerenciador de pacotes nao identificado. Instale manualmente:"
    echo "    - python3, python3-pip, python3-venv"
    echo "    - libssl-dev, libffi-dev, libxml2-dev, libxslt1-dev"
    echo "    - openssl, p11-kit"
    exit 1
fi

echo ""
echo "[*] Criando ambiente virtual..."
python3 -m venv venv
source venv/bin/activate

echo "[*] Atualizando pip..."
pip install --upgrade pip

echo ""
echo "[*] Instalando dependencias Python..."
pip install -r backend/requirements.txt

echo ""
echo "[*] Verificando dependencias..."
python3 -c "import lxml; import OpenSSL; import signxml; import cryptography; print('OK')"

echo ""
echo "=== Instalacao concluida ==="
echo "Ative o ambiente com: source venv/bin/activate"
