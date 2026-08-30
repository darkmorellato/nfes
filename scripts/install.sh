#!/usr/bin/env bash
# Instala o .AppImage no menu do usuário (modo "instalado", além do portátil).
set -e

APP="nfe-manager"
REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
APPIMAGE="$(ls "${REPO_DIR}"/NFE-Manager*.AppImage 2>/dev/null | head -1 || true)"

mkdir -p "$HOME/.local/share/applications" "$HOME/.local/share/icons/hicolor/256x256/apps"

# Instala ícone
if [ -f "${REPO_DIR}/AppDir/nfe-manager.png" ]; then
    cp "${REPO_DIR}/AppDir/nfe-manager.png" "$HOME/.local/share/icons/hicolor/256x256/apps/nfe-manager.png"
    gtk-update-icon-cache "$HOME/.local/share/icons/hicolor" 2>/dev/null || true
fi

EXEC_CMD="${REPO_DIR}/venv/bin/python3 ${REPO_DIR}/app_launcher.py"

cat > "$HOME/.local/share/applications/${APP}.desktop" <<EOF
[Desktop Entry]
Name=NFE Manager
Comment=Portal NF-e local (SEFAZ) sem Java
Exec=${EXEC_CMD}
Path=${REPO_DIR}
Icon=nfe-manager
Type=Application
Categories=Office;Finance;
Terminal=false
StartupNotify=true
StartupWMClass=nfe-manager
EOF

update-desktop-database "$HOME/.local/share/applications" 2>/dev/null || true
echo "Instalado com sucesso! Atalho: $HOME/.local/share/applications/${APP}.desktop"
