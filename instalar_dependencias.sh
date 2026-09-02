#!/usr/bin/env bash
# ==============================================================================
# NFE Manager — Instalador Universal de Dependências do Sistema (Linux)
# Detecta automaticamente: Ubuntu, Debian, Mint, Arch, Manjaro, Fedora, openSUSE
# ==============================================================================

set -e

echo "==============================================================================="
echo "        🏛️ NFE MANAGER — INSTALADOR AUTOMÁTICO DE DEPENDÊNCIAS"
echo "==============================================================================="
echo ""

# 1. Detecta o gerenciador de pacotes
if command -v apt-get &>/dev/null; then
    echo "🐧 Sistema Debian / Ubuntu / Mint / Zorin detectado!"
    echo "Instalando pacotes do sistema via apt..."
    sudo apt update
    sudo apt install -y python3 python3-venv python3-pip openssl libxml2 libxslt1-dev libxmlsec1-dev libxmlsec1-openssl pkg-config build-essential

elif command -v pacman &>/dev/null; then
    echo "🏹 Sistema Arch Linux / Manjaro / CachyOS / EndeavourOS detectado!"
    echo "Instalando pacotes do sistema via pacman..."
    sudo pacman -Syu --needed --noconfirm python python-pip openssl libxml2 libxslt xmlsec base-devel

elif command -v dnf &>/dev/null; then
    echo "🎩 Sistema Fedora / RHEL / AlmaLinux detectado!"
    echo "Instalando pacotes do sistema via dnf..."
    sudo dnf install -y python3 python3-pip python3-devel openssl libxml2-devel libxslt-devel xmlsec1-devel xmlsec1-openssl-devel gcc

elif command -v zypper &>/dev/null; then
    echo "🦎 Sistema openSUSE detectado!"
    echo "Instalando pacotes do sistema via zypper..."
    sudo zypper install -y python3 python3-pip python3-devel libxml2-devel libxslt-devel xmlsec1-devel gcc

else
    echo "⚠️ Gerenciador de pacotes não reconhecido automaticamente."
    echo "Certifique-se de instalar manualmente: python3, python3-venv, pip, openssl, libxml2 e libxslt."
fi

echo ""
echo "✅ Dependências do sistema instaladas com sucesso!"
echo "Agora você pode iniciar o sistema com: ./iniciar_linux.sh"
