#!/usr/bin/env bash
# ============================================================================
# NFE Manager — Instalador de Atalho Desktop (.desktop) e Ícones do Sistema
# ============================================================================
set -euo pipefail

APP="nfe-manager"
REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

# Diretórios de destino do usuário (padrão XDG)
APPS_DIR="${HOME}/.local/share/applications"
ICON_DIR="${HOME}/.local/share/icons/hicolor/256x256/apps"
PIXMAPS_DIR="${HOME}/.local/share/pixmaps"
DESKTOP_DIR="$(xdg-user-dir DESKTOP 2>/dev/null || echo "${HOME}/Desktop")"

mkdir -p "${APPS_DIR}" "${ICON_DIR}" "${PIXMAPS_DIR}"

# 1. Localiza a melhor imagem de ícone (favicon.png ou AppDir/nfe-manager.png)
ICON_SRC=""
if [ -f "${REPO_DIR}/frontend/favicon.png" ]; then
    ICON_SRC="${REPO_DIR}/frontend/favicon.png"
elif [ -f "${REPO_DIR}/AppDir/nfe-manager.png" ]; then
    ICON_SRC="${REPO_DIR}/AppDir/nfe-manager.png"
fi

if [ -n "${ICON_SRC}" ] && [ -f "${ICON_SRC}" ]; then
    cp "${ICON_SRC}" "${ICON_DIR}/${APP}.png"
    cp "${ICON_SRC}" "${PIXMAPS_DIR}/${APP}.png"
    gtk-update-icon-cache "${HOME}/.local/share/icons/hicolor" 2>/dev/null || true
fi

# 2. Define o comando de execução com o Python do ambiente virtual
PYTHON_BIN="${REPO_DIR}/venv/bin/python"
if [ ! -f "${PYTHON_BIN}" ]; then
    PYTHON_BIN="$(command -v python3 || echo "python3")"
fi

EXEC_CMD="${PYTHON_BIN} ${REPO_DIR}/app_launcher.py"
ICON_PATH="${ICON_DIR}/${APP}.png"

# 3. Cria o arquivo .desktop no menu de aplicativos
DESKTOP_FILE="${APPS_DIR}/${APP}.desktop"
cat > "${DESKTOP_FILE}" <<EOF
[Desktop Entry]
Version=1.0
Name=NFE Manager
GenericName=Gestão e Emissão de NF-e
Comment=Portal NF-e local autônomo (SEFAZ) sem Java
Exec=${EXEC_CMD}
Path=${REPO_DIR}
Icon=${ICON_PATH}
Terminal=false
Type=Application
Categories=Office;Finance;
StartupNotify=true
StartupWMClass=nfe-manager
Keywords=nfe;sefaz;nota fiscal;danfe;impostos;
EOF

chmod +x "${DESKTOP_FILE}"
update-desktop-database "${APPS_DIR}" 2>/dev/null || true

# 4. Copia opcionalmente para a Área de Trabalho se ela existir
if [ -d "${DESKTOP_DIR}" ]; then
    cp "${DESKTOP_FILE}" "${DESKTOP_DIR}/${APP}.desktop"
    chmod +x "${DESKTOP_DIR}/${APP}.desktop"
    # Marca como confiável no GNOME/Ubuntu se gio estiver disponível
    gio set "${DESKTOP_DIR}/${APP}.desktop" metadata::trusted true 2>/dev/null || true
fi

echo "✅ Atalho e ícone instalados com sucesso!"
echo "   - Menu de Aplicativos: ${DESKTOP_FILE}"
[ -d "${DESKTOP_DIR}" ] && echo "   - Área de Trabalho:    ${DESKTOP_DIR}/${APP}.desktop"

