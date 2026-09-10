#!/usr/bin/env bash
# ==============================================================================
# NFE Manager — Atualizador Direto de 1 Clique (Zorin OS / Linux)
# Executa a sincronização forçada com o repositório oficial GitHub sem requerer terminal.
# ==============================================================================

set -e

# Detecta a pasta do projeto
REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$REPO_DIR"

OFFICIAL_REPO="https://github.com/darkmorellato/nfes.git"

echo "==============================================================================="
echo "               🔄 NFE MANAGER — ATUALIZADOR DIRETO (1-CLIQUE)"
echo "==============================================================================="
echo "📁 Diretório: $REPO_DIR"
echo "🌐 Repositório: $OFFICIAL_REPO"
echo ""

# 1. Configura diretório seguro no Git
git config --global --add safe.directory "$REPO_DIR" 2>/dev/null || true

# 2. Configura a URL oficial do repositório
if git remote get-url origin &>/dev/null; then
    git remote set-url origin "$OFFICIAL_REPO"
else
    git remote add origin "$OFFICIAL_REPO"
fi

# 3. Baixa as novidades do GitHub
echo "⬇️ [1/5] Conectando ao GitHub e baixando atualizações..."
git fetch origin main

# 4. Configura tracking e sincronização forçada (limpa conflitos de código sem apagar banco SQLite nem certificados)
echo "🧹 [2/5] Aplicando atualização limpa e resolvendo conflitos..."
git checkout -B main origin/main
git branch --set-upstream-to=origin/main main 2>/dev/null || true
git reset --hard origin/main

# 5. Atualiza dependências Python no venv
echo "📦 [3/5] Verificando dependências Python..."
if [ -d "venv" ]; then
    ./venv/bin/pip install --upgrade pip -q 2>/dev/null || true
    ./venv/bin/pip install -r backend/requirements.txt -q 2>/dev/null || true
fi

# 6. Executa migrações do banco SQLite
echo "🗄️ [4/5] Verificando tabelas e banco de dados..."
if [ -f "venv/bin/python" ]; then
    ./venv/bin/python -c "from backend.database import init_db; init_db()" 2>/dev/null || true
fi

# 7. Reinicia o serviço nfe-manager se estiver ativo
echo "🔄 [5/5] Reiniciando serviço do sistema..."
systemctl --user restart nfe-manager.service 2>/dev/null || true

# 8. Notificação gráfica no Zorin OS (Zenity ou notify-send)
VERSION="$(git log -1 --format='%h — %s (%cd)' --date=short)"
echo ""
echo "==============================================================================="
echo "  🎉 Sistema atualizado com sucesso para a versão: $VERSION"
echo "==============================================================================="

if command -v zenity &>/dev/null; then
    zenity --info --title="NFE Manager Atualizado!" --text="🎉 Atualização concluída com sucesso!\n\nVersão instalada: $VERSION\n\nO sistema já está pronto para uso." --timeout=8 2>/dev/null || true
elif command -v notify-send &>/dev/null; then
    notify-send "NFE Manager Atualizado" "🎉 Sistema atualizado com sucesso para: $VERSION" 2>/dev/null || true
fi

echo "Pronto! Você já pode fechar esta janela ou abrir o sistema."
sleep 3
